
#!/usr/bin/env python3
import argparse, fnmatch, hashlib, json, os, shutil
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image, ExifTags
    _PIL_OK = True
except Exception:
    _PIL_OK = False

CATEGORIES = {
    "Images": {".jpg",".jpeg",".png",".webp",".gif",".bmp",".tif",".tiff",".heic",".psd",".ai",".svg",".raw",".cr2",".nef",".arw"},
    "Videos": {".mp4",".mov",".mkv",".avi",".wmv",".flv",".webm",".mts",".m2ts",".m4v",".3gp"},
    "Audio": {".mp3",".wav",".flac",".aac",".ogg",".m4a",".wma",".aiff"},
    "Documents": {".txt",".rtf",".md",".doc",".docx",".odt",".pdf"},
    "Spreadsheets": {".xls",".xlsx",".csv",".ods"},
    "Presentations": {".ppt",".pptx",".key",".odp"},
    "Archives": {".zip",".rar",".7z",".tar",".gz",".bz2",".xz",".iso"},
    "Code": {".py",".js",".ts",".tsx",".jsx",".java",".c",".cpp",".cs",".go",".rb",".php",".sh",".ps1",".bat",".json",".yaml",".yml",".toml",".ini",".sql"},
    "Design": {".indd",".idml",".sketch",".fig",".xd"},
    "Fonts": {".ttf",".otf",".woff",".woff2"},
    "CAD_3D": {".dwg",".dxf",".step",".stp",".iges",".igs",".obj",".stl",".fbx",".rvt",".rfa"},
    "Disk_Images": {".dmg",".vhd",".vhdx",".vmdk"},
    "Installers": {".msi",".exe",".pkg",".deb",".rpm",".apk"},
    "System_Logs": {".log",".evtx",".dmp"},
}
def _sha_short(path: Path, chunk=4*1024*1024):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()[:10]
def _guess_cat(ext:str)->str:
    e = ext.lower()
    for k,v in CATEGORIES.items():
        if e in v: return k
    return "Other"
def _ensure(p:Path): p.mkdir(parents=True, exist_ok=True)
def _log(undo:Path|None, action:str, src:Path, dst:Path):
    if not undo: return
    _ensure(undo.parent)
    rec = {"time": datetime.utcnow().isoformat()+"Z","action": action,"src": str(src),"dst": str(dst)}
    with undo.open("a", encoding="utf-8") as f: f.write(json.dumps(rec)+"\n")
def _ignore(path:Path, globs): 
    posix = path.as_posix()
    return any(fnmatch.fnmatch(posix, g) for g in (globs or []))

_EXIF_MODEL_TAG = None
if _PIL_OK:
    try:
        for k,v in ExifTags.TAGS.items():
            if v=="Model": _EXIF_MODEL_TAG = k; break
    except Exception: _EXIF_MODEL_TAG = None
def _cam_model(p:Path)->str:
    if not (_PIL_OK and _EXIF_MODEL_TAG is not None): return ""
    try:
        with Image.open(p) as im:
            ex = im._getexif() or {}
            val = ex.get(_EXIF_MODEL_TAG, "")
            try:
                return (val.decode("utf-8") if isinstance(val,bytes) else str(val)).strip()
            except Exception:
                return str(val)
    except Exception:
        return ""

def _load_overrides(path:Path):
    if not path or not path.exists():
        return {"by_extension": {}, "by_glob": {}, "by_exif": {"camera_to": {}}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        by_exif = data.get("by_exif", {}) or {}
        if "camera_to" not in by_exif: by_exif["camera_to"] = {}
        return {
            "by_extension": data.get("by_extension", {}) or {},
            "by_glob": data.get("by_glob", {}) or {},
            "by_exif": by_exif
        }
    except Exception:
        return {"by_extension": {}, "by_glob": {}, "by_exif": {"camera_to": {}}}

def _route(src:Path, rel:Path, ext:str, overrides:dict)->Path:
    posix = rel.as_posix() if rel else src.name
    for pat,target in overrides.get("by_glob",{}).items():
        if fnmatch.fnmatch(posix, pat): return Path(target.replace("\\","/"))
    if ext.lower() in CATEGORIES["Images"] and overrides.get("by_exif",{}).get("camera_to"):
        cam = _cam_model(src)
        if cam:
            for key, target in overrides["by_exif"]["camera_to"].items():
                if key.lower() in cam.lower():
                    return Path(target.replace("{camera}", cam).replace("\\","/"))
    if ext.lower() in overrides.get("by_extension",{}):
        return Path(overrides["by_extension"][ext.lower()].replace("\\","/"))
    return Path(_guess_cat(ext))

def _safe_move(src:Path, dst:Path, *, dry:bool, undo:Path|None):
    try:
        _ensure(dst.parent)
        final = dst
        if final.exists():
            stem,ext = final.stem, final.suffix
            final = final.with_name(f"{stem}-{_sha_short(src)}{ext}")
        if dry:
            print(f"[DRY-RUN] MOVE: {src} -> {final}")
        else:
            shutil.move(str(src), str(final))
            _log(undo, "move", src, final)
            print(f"MOVED: {src} -> {final}")
    except (FileNotFoundError, OSError, PermissionError) as e:
        print(f"[ERROR] Cannot move {src}: {e}")

def organize(source:Path, dest:Path, *, preserve:bool, overrides_path:Path|None, ignore_globs, dry:bool, undo:Path|None):
    ov = _load_overrides(overrides_path)
    n=0
    for p in source.rglob("*"):
        if p.is_dir() or _ignore(p, ignore_globs): continue
        try:
            # Verify file is accessible before attempting to move
            if not p.exists():
                print(f"[WARN] File no longer exists: {p}")
                continue
            rel = p.relative_to(source) if preserve else Path(p.name)
            target_dir = _route(p, rel, p.suffix, ov)
            _safe_move(p, dest/target_dir/rel, dry=dry, undo=undo); n+=1
        except (FileNotFoundError, OSError, PermissionError) as e:
            print(f"[ERROR] Cannot process {p}: {e}")
            continue
    print(f"Processed {n} files.")

def _load_jsonl(path:Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s=line.strip()
            if s: yield json.loads(s)

def tag_rules(source:Path, rules_path:Path, out_jsonl:Path, ignore_globs):
    txt = rules_path.read_text(encoding="utf-8")
    lines = [ln.rstrip() for ln in txt.splitlines()]
    rules=[]; cur=None
    def flush():
        nonlocal cur
        if cur: rules.append(cur); cur=None
    for ln in lines:
        s=ln.strip()
        if s.startswith("- name:"):
            flush(); cur={"name":s.split(":",1)[1].strip().strip("'\""),"include":[],"exclude":[],"tags":[]}
        elif s.startswith("include:") and cur is not None:
            inner=s.split(":",1)[1].strip(); cur["include"]=[x.strip().strip("'\"") for x in inner[1:-1].split(",")] if inner.startswith("[") else []
        elif s.startswith("exclude:") and cur is not None:
            inner=s.split(":",1)[1].strip(); cur["exclude"]=[x.strip().strip("'\"") for x in inner[1:-1].split(",")] if inner.startswith("[") else []
        elif s.startswith("tags:") and cur is not None:
            inner=s.split(":",1)[1].strip(); cur["tags"]=[x.strip().strip("'\"") for x in inner[1:-1].split(",")] if inner.startswith("[") else []
    flush()
    tagged=[]
    for p in source.rglob("*"):
        if p.is_dir() or _ignore(p, ignore_globs): continue
        rel = p.relative_to(source).as_posix()
        tags=set()
        for r in rules:
            inc_ok = any(fnmatch.fnmatch(rel, pat) for pat in r.get("include",[])) if r.get("include") else False
            exc_ok = any(fnmatch.fnmatch(rel, pat) for pat in r.get("exclude",[])) if r.get("exclude") else False
            if inc_ok and not exc_ok:
                for t in r.get("tags",[]): 
                    if t: tags.add(t)
        if tags:
            tagged.append({"path": str(p.resolve()), "rel": rel, "tags": sorted(tags), "timestamp": datetime.utcnow().isoformat()+"Z"})
    _ensure(out_jsonl.parent)
    with out_jsonl.open("w", encoding="utf-8") as f:
        for rec in tagged: f.write(json.dumps(rec, ensure_ascii=False)+"\n")
    print(f"Tagged {len(tagged)} files → {out_jsonl}")

def move_by_tags(source:Path, dest:Path, tags_jsonl:Path, req_tags:list[str], *, ignore_globs, dry:bool, undo:Path|None):
    want=set(t.strip() for t in req_tags if t.strip()); n=0
    for rec in _load_jsonl(tags_jsonl):
        src=Path(rec["path"])
        if _ignore(src, ignore_globs): continue
        if want.issubset(set(rec.get("tags",[]))):
            rel = Path(rec["rel"]).name
            _safe_move(src, dest/rel, dry=dry, undo=undo); n+=1
    print(f"Moved {n} files (tags={sorted(want)})")

def _select_keeper(group:list[dict], policy:str):
    if policy=="largest": return max(group, key=lambda r: r["size"])
    if policy=="newest":  return max(group, key=lambda r: r["mtime"])
    if policy=="shortestpath": return min(group, key=lambda r: len(r["path"]))
    return sorted(group, key=lambda r: r["path"])[0]

def _hardlink_replace(src:Path, keeper:Path):
    tmp = src.with_suffix(src.suffix+".to_delete")
    try:
        os.replace(src, tmp)
        os.link(keeper, src)
        tmp.unlink()
        return True
    except Exception as e:
        try:
            if src.exists(): src.unlink()
            os.replace(tmp, src)
        except Exception: pass
        print(f"[WARN] hardlink failed for {src}: {e}")
        return False

def dedupe(report:Path, quarantine:Path, *, keeper_policy:str, link_mode:str, ignore_globs, dry:bool, undo:Path|None):
    _ensure(quarantine)
    idx={}
    for rec in _load_jsonl(report):
        h=rec.get("sha256")
        if h: idx.setdefault(h, []).append(rec)
    groups=[g for g in idx.values() if len(g)>1]
    processed=0
    for g in groups:
        keeper_rec=_select_keeper(g, keeper_policy); keeper=Path(keeper_rec["path"])
        for rec in g:
            if rec is keeper_rec: continue
            src=Path(rec["path"])
            if _ignore(src, ignore_globs) or not src.exists(): continue
            if dry:
                print(f"[DRY-RUN] DEDUPE {link_mode.upper()}: {src}")
                processed+=1; continue
            if link_mode=="move":
                tgt=quarantine/src.name
                _safe_move(src, tgt, dry=False, undo=undo); processed+=1
            elif link_mode=="hardlink":
                if _hardlink_replace(src, keeper):
                    _log(undo, "hardlink_to", src, keeper); processed+=1
            elif link_mode=="copy":
                tmp = src.with_suffix(src.suffix+".to_delete")
                try:
                    os.replace(src, tmp)
                    _ensure(src.parent)
                    shutil.copy2(keeper, src)
                    tmp.unlink()
                    _log(undo, "copy_from", src, keeper)
                    processed+=1
                except Exception as e:
                    print(f"[WARN] copy failed for {src}: {e}")
            else:
                print(f"[WARN] unknown link_mode={link_mode}")
    print(f"Duplicate sets: {len(groups)} | Files processed: {processed}")

def main():
    ap = argparse.ArgumentParser(description="Organize, tag, move-by-tags, dedupe (undo log, EXIF routing, hardlink mode)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1=sub.add_parser("organize"); p1.add_argument("--source",required=True); p1.add_argument("--dest",required=True)
    p1.add_argument("--preserve-tree",action="store_true"); p1.add_argument("--category-overrides"); 
    p1.add_argument("--ignore-glob",default=""); p1.add_argument("--undo-log",default=""); p1.add_argument("--dry-run",action="store_true")
    p2=sub.add_parser("tag"); p2.add_argument("--source",required=True); p2.add_argument("--rules",required=True); p2.add_argument("--out",required=True); p2.add_argument("--ignore-glob",default="")
    p3=sub.add_parser("move"); p3.add_argument("--source",required=True); p3.add_argument("--dest",required=True); p3.add_argument("--tags-jsonl",required=True); p3.add_argument("--require-tags",required=True); p3.add_argument("--ignore-glob",default=""); p3.add_argument("--undo-log",default=""); p3.add_argument("--dry-run",action="store_true")
    p4=sub.add_parser("dedupe"); p4.add_argument("--report",required=True); p4.add_argument("--quarantine",required=True); p4.add_argument("--keeper",choices=["alpha","largest","newest","shortestpath"],default="alpha")
    p4.add_argument("--ignore-glob",default=""); p4.add_argument("--undo-log",default=""); p4.add_argument("--link-mode",choices=["move","hardlink","copy"],default="move"); p4.add_argument("--dry-run",action="store_true")
    a=ap.parse_args()
    if a.cmd=="organize":
        undo=Path(a.undo_log) if a.undo_log else None; ign=[g for g in a.ignore_glob.split(",") if g]
        organize(Path(a.source), Path(a.dest), preserve=a.preserve_tree, overrides_path=Path(a.category_overrides) if a.category_overrides else None, ignore_globs=ign, dry=a.dry_run, undo=undo)
    elif a.cmd=="tag":
        ign=[g for g in a.ignore_glob.split(",") if g]; tag_rules(Path(a.source), Path(a.rules), Path(a.out), ign)
    elif a.cmd=="move":
        undo=Path(a.undo_log) if a.undo_log else None; ign=[g for g in a.ignore_glob.split(",") if g]
        req=[t.strip() for t in a.require_tags.split(",") if t.strip()]
        move_by_tags(Path(a.source), Path(a.dest), Path(a.tags_jsonl), req, ignore_globs=ign, dry=a.dry_run, undo=undo)
    else:
        undo=Path(a.undo_log) if a.undo_log else None; ign=[g for g in a.ignore_glob.split(",") if g]
        dedupe(Path(a.report), Path(a.quarantine), keeper_policy=a.keeper, link_mode=a.link_mode, ignore_globs=ign, dry=a.dry_run, undo=undo)

if __name__ == "__main__": main()
