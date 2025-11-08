#!/usr/bin/env python3
# (Shortened docstring to fit tool limits; full version includes HTML table & CSV export)
import argparse, json, csv, fnmatch
from pathlib import Path

CATEGORIES = {"Images":{".jpg",".jpeg",".png",".webp",".gif",".bmp",".tif",".tiff",".heic",".psd",".ai",".svg",".raw",".cr2",".nef",".arw"},"Videos":{".mp4",".mov",".mkv",".avi",".wmv",".flv",".webm",".mts",".m2ts",".m4v",".3gp"},"Audio":{".mp3",".wav",".flac",".aac",".ogg",".m4a",".wma",".aiff"},"Documents":{".txt",".rtf",".md",".doc",".docx",".odt",".pdf"},"Spreadsheets":{".xls",".xlsx",".csv",".ods"},"Presentations":{".ppt",".pptx",".key",".odp"},"Archives":{".zip",".rar",".7z",".tar",".gz",".bz2",".xz",".iso"},"Code":{".py",".js",".ts",".tsx",".jsx",".java",".c",".cpp",".cs",".go",".rb",".php",".sh",".ps1",".bat",".json",".yaml",".yml",".toml",".ini",".sql"},"Design":{".indd",".idml",".sketch",".fig",".xd"},"Fonts":{".ttf",".otf",".woff",".woff2"},"CAD_3D":{".dwg",".dxf",".step",".stp",".iges",".igs",".obj",".stl",".fbx",".rvt",".rfa"},"Disk_Images":{".dmg",".vhd",".vhdx",".vmdk"},"Installers":{".msi",".exe",".pkg",".deb",".rpm",".apk"},"System_Logs":{".log",".evtx",".dmp"}}
def guess_category(ext): 
    for k,v in CATEGORIES.items():
        if ext.lower() in v: return k
    return "Other"
def load_overrides(path): 
    if not path: return {"by_extension":{},"by_glob":{}}
    try:
        data=json.loads(Path(path).read_text(encoding="utf-8"))
        return {"by_extension":data.get("by_extension",{}) or {}, "by_glob":data.get("by_glob",{}) or {}}
    except Exception: return {"by_extension":{},"by_glob":{}}
def apply_overrides(src, rel, ext, overrides):
    relp=rel.as_posix() if rel else src.name
    for pat,cat in overrides.get("by_glob",{}).items():
        if fnmatch.fnmatch(relp, pat): return cat
    if ext.lower() in overrides.get("by_extension",{}): return overrides["by_extension"][ext.lower()]
    return guess_category(ext)
def load_jsonl(path):
    with open(path,"r",encoding="utf-8") as f:
        for line in f:
            s=line.strip()
            if s: yield json.loads(s)
def human(n):
    u=["B","KB","MB","GB","TB"];i=0;x=float(n)
    while x>=1024 and i<len(u)-1: x/=1024;i+=1
    return f"{x:.2f} {u[i]}"
def preview_tags(source,dest,tags_jsonl,req):
    reqs=set(t.strip() for t in req if t.strip()); rows=[]
    for rec in load_jsonl(tags_jsonl):
        tags=set(rec.get("tags",[]))
        if not reqs.issubset(tags): continue
        src=Path(rec["path"]);
        if not src.exists(): continue
        try:
            size = src.stat().st_size
            rows.append({"src":str(src),"dest":str(dest/Path(rec["rel"]).name),"size":size,"tags":", ".join(sorted(tags)),"category":""})
        except (FileNotFoundError, OSError, PermissionError) as e:
            print(f"[WARN] Skipping inaccessible file: {src} ({e})")
            continue
    return rows,f"Require tags: {', '.join(sorted(reqs))}"
def preview_organize(source,dest,preserve,overrides_path=None):
    ov=load_overrides(overrides_path) if overrides_path else {"by_extension":{},"by_glob":{}}
    rows=[]
    for p in Path(source).rglob("*"):
        if p.is_dir(): continue
        try:
            size = p.stat().st_size
            rel=p.relative_to(source) if preserve else Path(p.name)
            cat=apply_overrides(p,rel,p.suffix,ov)
            rows.append({"src":str(p),"dest":str(Path(dest)/Path(cat)/rel),"size":size,"tags":"","category":cat})
        except (FileNotFoundError, OSError, PermissionError) as e:
            # Skip files that can't be accessed (OneDrive placeholders, locked files, etc.)
            print(f"[WARN] Skipping inaccessible file: {p} ({e})")
            continue
    return rows,f"Organize by category ({'preserve tree' if preserve else 'flat'})"
def build_html(rows,source,dest,subtitle):
    rows=sorted(rows,key=lambda r:(r["dest"].lower(),r["src"].lower()))
    html=["<!DOCTYPE html><html><head><meta charset='utf-8'><title>Move Preview</title>",
          "<style>body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;margin:24px}table{width:100%;border-collapse:collapse;margin-top:16px}th,td{border:1px solid #ddd;padding:8px;font-size:14px}th{background:#f7f7f7;text-align:left}.mono{font-family:ui-monospace,Menlo,Consolas,monospace;color:#555}</style>",
          "</head><body>", f"<h1>Move Preview</h1><div>{subtitle}</div>",
          f"<div class='mono'>Source: {source}<br>Dest: {dest}</div>",
          "<table><thead><tr><th>#</th><th>Current Path</th><th>Proposed Destination</th><th>Size</th><th>Tags</th><th>Category</th></tr></thead><tbody>"]
    for i,r in enumerate(rows,1):
        html.append(f"<tr><td>{i}</td><td class='mono'>{r['src']}</td><td class='mono'>{r['dest']}</td><td>{human(r['size'])}</td><td>{r['tags']}</td><td>{r['category']}</td></tr>")
    html.append("</tbody></table></body></html>")
    return "\n".join(html)
def write_csv(rows,path):
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["src","dest","size","category","tags"]); w.writeheader(); [w.writerow(r) for r in rows]
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",required=True,choices=["tags","organize"]); ap.add_argument("--source",required=True); ap.add_argument("--dest",required=True); ap.add_argument("--out",required=True); ap.add_argument("--csv-out")
    ap.add_argument("--tags-jsonl"); ap.add_argument("--require-tags")
    ap.add_argument("--preserve-tree",action="store_true"); ap.add_argument("--category-overrides")
    a=ap.parse_args()
    source=Path(a.source); dest=Path(a.dest)
    if a.mode=="tags":
        rows,sub=preview_tags(source,dest,Path(a.tags_jsonl),a.require_tags.split(","))
    else:
        rows,sub=preview_organize(source,dest,a.preserve_tree,Path(a.category_overrides) if a.category_overrides else None)
    html=build_html(rows,source,dest,sub); Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(html,encoding="utf-8")
    if a.csv_out: write_csv(rows,a.csv_out)
    print(f"Report written: {a.out}")
if __name__=="__main__": main()
