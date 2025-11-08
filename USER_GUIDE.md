# Drive Cleanup Toolkit v3 - User Guide

## Getting Started

### 1. First Time Setup

```powershell
# Navigate to project folder
cd U:\Dev\utilities\DriveCleanupToolkit_v3

# Activate virtual environment
.\venv\Scripts\Activate.ps1
# Or use the helper script
. .\activate.ps1
```

### 2. Quick Launch

**GUI Mode (Recommended for beginners):**
```powershell
python gui_toolkit.py
```

**Command Line Mode:**
```powershell
# See all commands
python drive_organizer.py --help
python scan_storage.py --help
```

## Common Workflows

### Workflow 1: Scan and Find Duplicates

```powershell
# Step 1: Scan your drive
python scan_storage.py "C:\MyFiles" --out "./reports" --image-phash --text-hash

# Step 2: Generate duplicate report
python duplicates_report.py --report "./reports/scan_report.jsonl" --out duplicates.html --csv duplicates.csv

# Step 3: Review duplicates.html in browser
# Step 4: Deduplicate (dry-run first!)
python drive_organizer.py dedupe --report "./reports/scan_report.jsonl" --quarantine "C:\Quarantine" --keeper newest --link-mode move --dry-run

# Step 5: Run for real (remove --dry-run)
python drive_organizer.py dedupe --report "./reports/scan_report.jsonl" --quarantine "C:\Quarantine" --keeper newest --link-mode move --undo-log "./undo.jsonl"
```

### Workflow 2: Organize Files by Category

```powershell
# Step 1: Preview the organization
python move_preview_report.py --mode organize --source "C:\MyFiles" --dest "C:\Organized" --out preview.html --preserve-tree --category-overrides overrides.json

# Step 2: Review preview.html
# Step 3: Organize (dry-run first!)
python drive_organizer.py organize --source "C:\MyFiles" --dest "C:\Organized" --preserve-tree --category-overrides overrides.json --dry-run

# Step 4: Run for real
python drive_organizer.py organize --source "C:\MyFiles" --dest "C:\Organized" --preserve-tree --category-overrides overrides.json --undo-log "./undo.jsonl"
```

### Workflow 3: Tag-Based Organization

```powershell
# Step 1: Edit rules.yaml with your tagging rules
# Step 2: Tag files based on rules
python drive_organizer.py tag --source "C:\MyFiles" --rules rules.yaml --out tagged.jsonl

# Step 3: Preview moves by tags
python move_preview_report.py --mode tags --source "C:\MyFiles" --dest "C:\Projects" --tags-jsonl tagged.jsonl --require-tags "work,docs" --out preview.html

# Step 4: Move files with specific tags
python drive_organizer.py move --source "C:\MyFiles" --dest "C:\Projects" --tags-jsonl tagged.jsonl --require-tags "work,docs" --dry-run

# Step 5: Execute
python drive_organizer.py move --source "C:\MyFiles" --dest "C:\Projects" --tags-jsonl tagged.jsonl --require-tags "work,docs" --undo-log "./undo.jsonl"
```

## Configuration Files

### overrides.json
Customize file categorization:

```json
{
  "by_extension": {
    ".heic": "Images/Phone/HEIC",
    ".pdf": "Documents/PDFs"
  },
  "by_glob": {
    "**/iPhone/**": "Images/Phone",
    "**/Scans/**": "Documents/Scans"
  },
  "by_exif": {
    "camera_to": {
      "Canon": "Images/RAW/{camera}",
      "NIKON": "Images/RAW/{camera}"
    }
  }
}
```

### rules.yaml
Define tagging rules:

```yaml
- name: Work Documents
  include: ["**/Projects/**", "**/*.doc", "**/*.docx"]
  exclude: ["**/_Trash/**"]
  tags: ["work", "docs"]

- name: Family Photos 2024
  include: ["**/Photos/2024/**", "**/*2024*.*"]
  tags: ["photos", "family", "2024"]
```

## Safety Tips

1. **Always use `--dry-run` first** - See what will happen without making changes
2. **Create preview reports** - Review HTML reports before executing
3. **Use `--undo-log`** - Create undo logs for all operations
4. **Keep backups** - Copy important files before deduplication
5. **Test on small folders first** - Verify behavior before processing large drives

## Deduplication Modes

- **`move`** - Moves duplicates to quarantine (safest, can manually review)
- **`hardlink`** - Replaces duplicates with hard links (saves space, keeps file accessible)
- **`copy`** - Replaces duplicates with copies of keeper (maintains separate files)

## Keeper Policies

- **`newest`** - Keep the most recently modified file
- **`largest`** - Keep the largest file
- **`alpha`** - Keep alphabetically first file path
- **`shortestpath`** - Keep file with shortest path

## Undo Operations

If something goes wrong:

```powershell
# Undo moves
python undo_moves.py --log "./undo.jsonl" --dry-run

# Undo with backup restoration
python undo_moves.py --log "./undo.jsonl" --force-copy-from "C:\Backup" --dry-run

# Execute undo (remove --dry-run)
python undo_moves.py --log "./undo.jsonl"
```

## Troubleshooting

**Issue: "Module not found"**
```powershell
# Make sure virtual environment is activated
.\venv\Scripts\Activate.ps1
# Reinstall if needed
pip install -r requirements.txt
```

**Issue: "Permission denied"**
- Run PowerShell as Administrator
- Check file permissions
- Ensure files aren't locked by other programs

**Issue: Scan is slow**
- Use `--max-files` to limit scope for testing
- Disable expensive options like `--fuzzy` for initial scans
- Hash cache speeds up subsequent scans

## Advanced Options

### Scan Options
- `--follow-symlinks` - Follow symbolic links
- `--min-size` / `--max-size` - Filter by file size
- `--skip-ext` - Skip extensions (comma-separated)
- `--skip-glob` - Skip patterns (comma-separated)
- `--hash-large` - Hash files larger than 200MB

### Organization Options
- `--preserve-tree` - Maintain original folder structure
- `--ignore-glob` - Skip files matching patterns

## GUI Interface

The GUI provides a professional file manager-style interface with:

### Main Tabs
- **Scan** - Index and analyze files with progress tracking
  - Real-time progress bar during scans
  - Configure hash options and output location
- **Results** - View scan results in sortable tree view
  - Columns: Path, Size, Modified, Hash, Type
  - Sort by clicking column headers
  - Right-click context menu to open files/folders
  - Filter and search capabilities
- **Preview** - Generate move preview reports before organizing
  - HTML/CSV output options
  - Preview by category or tags
- **Organize** - Categorize files automatically
  - Category-based organization with overrides
  - Preserve tree structure option
  - Dry-run mode for safety
- **Dedupe** - Remove duplicate files
  - Multiple keeper policies (newest, largest, etc.)
  - Link modes: move, hardlink, copy
  - Quarantine location for removed duplicates
- **Undo** - Reverse operations using undo logs
  - Load and restore from undo.jsonl files
  - Dry-run preview before undoing

### Features
- **Menu Bar** - File menu (Open Report, Exit) and Help menu (About, User Guide)
- **Status Bar** - Shows current operation status
- **Log Panel** - Collapsible output window showing command execution
- **Threading** - All operations run in background threads to keep UI responsive
- **Context Menus** - Right-click files in Results tab to open or explore folder

All long-running operations display progress and output in real-time without freezing the interface.
