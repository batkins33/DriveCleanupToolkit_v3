#!/usr/bin/env python3
import argparse, json, shutil
from pathlib import Path
def _iter_log(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s=line.strip()
            if s: yield json.loads(s)
def main():
    ap=argparse.ArgumentParser(description="Replay undo actions from drive_organizer.py")
    ap.add_argument("--log", required=True); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force-copy-from", default="")
    a=ap.parse_args()
    entries=list(_iter_log(Path(a.log))); entries.reverse()
    for rec in entries:
        act, src, dst = rec.get("action"), Path(rec.get("src","")), Path(rec.get("dst",""))
        if act=="move":
            if a.dry_run: print(f"[DRY-RUN] UNDO MOVE: {dst} -> {src}")
            else:
                if dst.exists(): src.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(dst), str(src)); print(f"UNDONE: {dst} -> {src}")
                else: print(f"[WARN] Missing {dst}; cannot undo move")
        elif act in ("hardlink_to","copy_from"):
            if not a.force_copy_from: print(f"[INFO] No-op for {act} at {src} (provide --force-copy-from)")
            else:
                backup=Path(a.force_copy_from)/src.name
                if backup.exists():
                    if a.dry_run: print(f"[DRY-RUN] RESTORE {src} from {backup}")
                    else: src.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(str(backup), str(src)); print(f"RESTORED {src} from {backup}")
                else: print(f"[WARN] Backup not found for {src}")
        else: print(f"[WARN] Unknown action: {act}")
if __name__=="__main__": main()
