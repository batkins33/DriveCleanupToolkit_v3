# Drive Cleanup Toolkit — v3

A comprehensive Python toolkit for organizing, deduplicating, and managing files on drives. Features intelligent categorization, tag-based organization, duplicate detection with multiple algorithms, and a graphical user interface.

## Features

- 🗂️ **Smart Organization** - Automatically categorize files by type with customizable rules
- 🔍 **Duplicate Detection** - SHA-256, perceptual hashing, text similarity, and fuzzy hashing
- 🏷️ **Tag-Based System** - Flexible tagging rules with glob patterns
- 📊 **Preview Reports** - HTML/CSV reports before making changes
- ↩️ **Undo System** - Safety net with JSONL undo logs
- 🖼️ **EXIF Routing** - Organize photos by camera model
- 🔗 **Deduplication Modes** - Move, hardlink, or copy-based deduplication
- 🎨 **GUI Interface** - Professional Tkinter interface with tree view results, progress tracking, and threaded operations
- 💾 **SQLite Cache** - Fast re-scanning with hash caching

## Quick Start

### 1. Setup Virtual Environment

```powershell
# Create virtual environment
python -m venv venv

# Activate it (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Or (Windows CMD)
venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the GUI

```powershell
python gui_toolkit.py
```

### 3. Or Use Command Line

**Scan a folder:**
```powershell
python scan_storage.py "C:\MyFolder" --out "./reports" --image-phash --text-hash
```

**Preview organization:**
```powershell
python move_preview_report.py --mode organize --source "C:\MyFolder" --dest "C:\Organized" --out preview.html --preserve-tree --category-overrides overrides.json
```

**Organize files (with dry-run first!):**
```powershell
python drive_organizer.py organize --source "C:\MyFolder" --dest "C:\Organized" --preserve-tree --category-overrides overrides.json --dry-run
```

**Generate duplicate report:**
```powershell
python duplicates_report.py --report "./reports/scan_report.jsonl" --out duplicates.html --csv duplicates.csv
```

**Deduplicate (moves to quarantine):**
```powershell
python drive_organizer.py dedupe --report "./reports/scan_report.jsonl" --quarantine "C:\Quarantine" --keeper newest --link-mode move --dry-run
```

## Configuration Files

- **`overrides.json`** - Custom category routing rules
- **`rules.yaml`** - Tag assignment rules for pattern matching

## Safety Features

- All operations support `--dry-run` flag
- Undo logs in JSONL format
- Preview reports before executing
- Backup restoration via `undo_moves.py`

## Documentation

See `USER_GUIDE.md` for detailed usage examples and `IMPLEMENTATION_GUIDE.md` for technical details.

## Requirements

- Python 3.8+
- See `requirements.txt` for dependencies
