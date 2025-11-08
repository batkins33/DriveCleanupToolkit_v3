# Quick Reference - Drive Cleanup Toolkit v3

## Daily Usage

```powershell
# Activate environment
.\venv\Scripts\Activate.ps1

# Launch GUI (easiest)
python gui_toolkit.py

# Or use command line...
```

## Most Common Commands

### 1. Scan Files
```powershell
python scan_storage.py "C:\YourFolder" --out "./reports"
```

### 2. Find Duplicates
```powershell
python duplicates_report.py --report "./reports/scan_report.jsonl" --out duplicates.html
```

### 3. Organize Files
```powershell
# Preview first
python move_preview_report.py --mode organize --source "C:\Source" --dest "C:\Dest" --out preview.html

# Then organize (with dry-run!)
python drive_organizer.py organize --source "C:\Source" --dest "C:\Dest" --dry-run

# Execute (remove --dry-run)
python drive_organizer.py organize --source "C:\Source" --dest "C:\Dest" --undo-log undo.jsonl
```

### 4. Remove Duplicates
```powershell
python drive_organizer.py dedupe --report "./reports/scan_report.jsonl" --quarantine "C:\Quarantine" --keeper newest --dry-run
```

### 5. Undo Last Operation
```powershell
python undo_moves.py --log undo.jsonl --dry-run
```

## Essential Flags

- `--dry-run` - Preview without changes (ALWAYS USE FIRST!)
- `--undo-log FILE` - Create undo log for safety
- `--preserve-tree` - Keep folder structure
- `--category-overrides FILE` - Use custom rules

## File Locations

- `requirements.txt` - Python dependencies
- `overrides.json` - Category routing rules
- `rules.yaml` - Tagging rules
- `venv/` - Virtual environment (don't commit)
- `reports/` - Scan outputs (auto-generated)

## Help

```powershell
python drive_organizer.py --help
python scan_storage.py --help
python duplicates_report.py --help
python move_preview_report.py --help
python undo_moves.py --help
```

## Safety Checklist

- [ ] Virtual environment activated?
- [ ] Used `--dry-run` first?
- [ ] Reviewed preview HTML report?
- [ ] Have backups of important files?
- [ ] Using `--undo-log` flag?
- [ ] Tested on small folder first?

## Common Issues

**"Module not found"** → Activate venv: `.\venv\Scripts\Activate.ps1`  
**"Permission denied"** → Run as Administrator  
**Slow scan** → Add `--max-files 1000` for testing  
**Undo failed** → Check undo.jsonl exists and files haven't moved

## Project Structure

```
DriveCleanupToolkit_v3/
├── venv/                  # Virtual environment
├── requirements.txt       # Dependencies
├── setup.py              # Package config
├── .gitignore            # Git exclusions
├── activate.ps1          # Quick activation
├── README.md             # Overview
├── USER_GUIDE.md         # Detailed guide
├── QUICKREF.md           # This file
├── overrides.json        # Custom rules
├── rules.yaml            # Tagging rules
├── drive_organizer.py    # Main tool
├── scan_storage.py       # Scanner
├── duplicates_report.py  # Dup reporter
├── move_preview_report.py # Preview generator
├── undo_moves.py         # Undo system
└── gui_toolkit.py        # GUI interface
```
