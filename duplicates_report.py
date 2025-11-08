#!/usr/bin/env python3
import argparse, json, csv
from pathlib import Path
from collections import defaultdict
def load_jsonl(p):
    with open(p,"r",encoding="utf-8") as f:
        for line in f:
            s=line.strip()
            if s: yield json.loads(s)
def human(n):
    u=["B","KB","MB","GB","TB"];i=0;x=float(n)
    while x>=1024 and i<len(u)-1: x/=1024;i+=1
    return f"{x:.2f} {u[i]}"
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--report",required=True); ap.add_argument("--out",required=True); ap.add_argument("--csv",default=""); ap.add_argument("--include-near",action="store_true")
    a=ap.parse_args()
    sg=defaultdict(list); tg=defaultdict(list); lg=defaultdict(list)
    for rec in load_jsonl(a.report):
        if rec.get("sha256"): sg[rec["sha256"]].append(rec)
        if a.include_near and rec.get("text_hash"): tg[rec["text_hash"]].append(rec)
        if a.include_near and rec.get("tlsh"): lg[rec["tlsh"]].append(rec)
    groups=[v for v in sg.values() if len(v)>1]
    groups.sort(key=lambda g: sum(x["size"] for x in g), reverse=True)
    if a.csv:
        with open(a.csv,"w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(["group_type","key","count","total_bytes","sample"])
            for k,items in sg.items():
                if len(items)>1: w.writerow(["sha256",k,len(items),sum(x["size"] for x in items),items[0]["path"]])
    html=["<!DOCTYPE html><html><head><meta charset='utf-8'><title>Duplicate Groups</title><style>body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;margin:24px}table{width:100%;border-collapse:collapse;margin-top:16px}th,td{border:1px solid #ddd;padding:8px;font-size:14px}th{background:#f7f7f7;text-align:left}.mono{font-family:ui-monospace,Menlo,Consolas,monospace;color:#555}</style></head><body>", f"<h1>Exact Duplicate Groups</h1>", "<table><thead><tr><th>#</th><th>Count</th><th>Total Size</th><th>Paths</th></tr></thead><tbody>"]
    for i,g in enumerate(groups,1):
        total=sum(x["size"] for x in g)
        html.append(f"<tr><td>{i}</td><td>{len(g)}</td><td>{human(total)}</td><td class='mono'>"+"<br>".join(x['path'] for x in g)+"</td></tr>")
    html.append("</tbody></table></body></html>"); Path(a.out).write_text("\n".join(html),encoding="utf-8"); print(f"HTML written: {a.out}"); 
    if a.csv: print(f"CSV written: {a.csv}")
if __name__=="__main__": main()
