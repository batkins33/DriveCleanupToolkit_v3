
#!/usr/bin/env python3
"""
scan_storage.py (with SQLite hash cache)
"""
import argparse, csv, fnmatch, hashlib, json, sqlite3
from pathlib import Path
from datetime import datetime

# Optional imports (guard)
try:
    from PIL import Image
    import imagehash
    _IMG_OK = True
except Exception:
    _IMG_OK = False

DOC_EXTS = {".pdf",".docx",".txt",".md",".rtf"}
IMG_EXTS = {".png",".jpg",".jpeg",".webp",".bmp",".tif",".tiff",".heic"}

def _sha256(path: Path, chunk=8*1024*1024):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()

def _tlsh(path: Path, chunk=2*1024*1024):
    try:
        import tlsh
        h = tlsh.Tlsh()
        with path.open("rb") as f:
            for b in iter(lambda: f.read(chunk), b""):
                h.update(b)
        h.final()
        return h.hexdigest()
    except Exception:
        return None

def _text_hash(path: Path, limit=200_000):
    try:
        ext = path.suffix.lower()
        if ext == ".pdf":
            from pdfminer.high_level import extract_text
            t = extract_text(str(path)) or ""
        elif ext == ".docx":
            import docx
            d = docx.Document(str(path))
            t = "\n".join(p.text for p in d.paragraphs)
        elif ext in (".txt",".md",".rtf"):
            t = path.read_text(encoding="utf-8", errors="ignore")
        else:
            return None
        t = " ".join(t.lower().split())[:limit]
        return hashlib.sha256(t.encode("utf-8")).hexdigest()
    except Exception:
        return None

def _phash(path: Path):
    if not _IMG_OK: return None
    try:
        with Image.open(path) as im:
            return str(imagehash.phash(im))
    except Exception:
        return None

def _human(b:int) -> str:
    u = ["B","KB","MB","GB","TB"]; i=0; x=float(b)
    while x>=1024 and i<len(u)-1: x/=1024; i+=1
    return f"{x:.2f} {u[i]}"

def _open_cache(db: Path):
    conn = sqlite3.connect(str(db))
    conn.execute("""CREATE TABLE IF NOT EXISTS filehash (
        path TEXT PRIMARY KEY,
        size INTEGER NOT NULL,
        mtime_ns INTEGER NOT NULL,
        sha256 TEXT
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_filehash_meta ON filehash(size,mtime_ns)")
    return conn

def _cache_get(conn, path: Path, size: int, mtime_ns: int):
    row = conn.execute("SELECT sha256,size,mtime_ns FROM filehash WHERE path=?", (str(path),)).fetchone()
    if not row: return None
    sha, s, m = row
    return sha if (s==size and m==mtime_ns) else None

def _cache_put(conn, path: Path, size: int, mtime_ns: int, sha: str):
    conn.execute("INSERT OR REPLACE INTO filehash(path,size,mtime_ns,sha256) VALUES (?,?,?,?)",
                 (str(path), size, mtime_ns, sha))

def _should_skip(p: Path, skip_exts, skip_globs, min_size, max_size):
    try: st = p.stat()
    except Exception: return True
    if min_size is not None and st.st_size < min_size: return True
    if max_size is not None and st.st_size > max_size: return True
    if p.suffix.lower() in skip_exts: return True
    posix = p.as_posix()
    return any(fnmatch.fnmatch(posix, pat) for pat in skip_globs)

def scan(root: Path, out: Path, *, follow_symlinks=False, max_files=None,
         min_size=None, max_size=None, skip_exts=None, skip_globs=None,
         hash_large=False, do_text=False, do_fuzzy=False, do_phash=False):
    out.mkdir(parents=True, exist_ok=True)
    report = out/"scan_report.jsonl"
    dupcsv = out/"duplicates.csv"
    nearcsv = out/"near_dupes.csv"
    cachedb = out/"hash_cache.sqlite3"

    skip_exts = set(e.strip().lower() for e in (skip_exts or []) if e.strip())
    skip_globs = [g.strip() for g in (skip_globs or []) if g.strip()]

    conn = _open_cache(cachedb)
    sha_groups, text_groups, tlsh_groups = {}, {}, {}

    n = 0
    with report.open("w", encoding="utf-8") as rep:
        for p in root.rglob("*"):
            if p.is_dir(): continue
            if not follow_symlinks and p.is_symlink(): continue
            if _should_skip(p, skip_exts, skip_globs, min_size, max_size): continue
            
            try:
                st = p.stat()
            except (FileNotFoundError, OSError, PermissionError) as e:
                print(f"[WARN] Cannot access {p}: {e}")
                continue
                
            size, mtime, mtime_ns = st.st_size, st.st_mtime, st.st_mtime_ns
            ext = p.suffix.lower()

            sha = None
            if size <= 200*1024*1024 or hash_large:
                cached = _cache_get(conn, p.resolve(), size, mtime_ns)
                if cached:
                    sha = cached
                else:
                    try:
                        sha = _sha256(p)
                        _cache_put(conn, p.resolve(), size, mtime_ns, sha)
                        if n % 100 == 0: conn.commit()
                    except (FileNotFoundError, OSError, PermissionError) as e:
                        print(f"[WARN] Cannot hash {p}: {e}")
                        sha = None

            ph = _phash(p) if (do_phash and ext in IMG_EXTS) else None
            th = _text_hash(p) if (do_text and ext in DOC_EXTS) else None
            tz = _tlsh(p) if do_fuzzy else None

            rec = {
                "path": str(p.resolve()), "size": size, "size_human": _human(size),
                "mtime": datetime.utcfromtimestamp(mtime).isoformat()+"Z",
                "mtime_ns": mtime_ns, "ext": ext, "is_symlink": p.is_symlink(),
                "sha256": sha, "image_phash": ph, "text_hash": th, "tlsh": tz
            }
            rep.write(json.dumps(rec, ensure_ascii=False)+"\n")

            if sha: sha_groups.setdefault(sha, []).append(rec)
            if th:  text_groups.setdefault(th, []).append(rec)
            if tz:  tlsh_groups.setdefault(tz, []).append(rec)

            n += 1
            if max_files and n>=max_files: break
    conn.commit(); conn.close()

    with dupcsv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["sha256","count","total_size_MB","paths_sample"])
        for k, items in sha_groups.items():
            if len(items) > 1:
                total = sum(i["size"] for i in items)/1024/1024
                w.writerow([k, len(items), f"{total:.2f}", ";".join(i["path"] for i in items[:5])])

    with nearcsv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["key_type","key","count","paths_sample"])
        for k, items in text_groups.items():
            if len(items) > 1: w.writerow(["text_hash", k, len(items), ";".join(i["path"] for i in items[:5])])
        for k, items in tlsh_groups.items():
            if len(items) > 1: w.writerow(["tlsh", k, len(items), ";".join(i["path"] for i in items[:5])])

    print(f"Scanned {n} files")
    print(f"Report: {report}")
    print(f"Duplicates: {dupcsv} | Near-dupes: {nearcsv}")
    print(f"Hash cache: {cachedb}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-files", type=int)
    ap.add_argument("--follow-symlinks", action="store_true")
    ap.add_argument("--min-size", type=int); ap.add_argument("--max-size", type=int)
    ap.add_argument("--skip-ext", default="")
    ap.add_argument("--skip-glob", default="")
    ap.add_argument("--hash-large", action="store_true")
    ap.add_argument("--text-hash", action="store_true")
    ap.add_argument("--fuzzy", action="store_true")
    ap.add_argument("--image-phash", action="store_true")
    args = ap.parse_args()
    scan(Path(args.root), Path(args.out),
         follow_symlinks=args.follow_symlinks, max_files=args.max_files,
         min_size=args.min_size, max_size=args.max_size,
         skip_exts=[s for s in args.skip_ext.split(",") if s],
         skip_globs=[g for g in args.skip_glob.split(",") if g],
         hash_large=args.hash_large, do_text=args.text_hash,
         do_fuzzy=args.fuzzy, do_phash=args.image_phash)
