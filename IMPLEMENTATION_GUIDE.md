# Drive Cleanup Toolkit v3 - Implementation Guide

## Architecture Overview

The toolkit is organized into 5 core modules and 1 GUI interface:

### Core Modules

#### 1. `scan_storage.py`
**Purpose**: File system scanning, hash calculation, and cache management

**Key Components**:
- **`scan()`** - Main entry point for scanning directories
  - Recursively walks directory tree
  - Calculates multiple hash types (SHA-256, perceptual, text, fuzzy)
  - Caches hashes in SQLite database for performance
  - Handles OneDrive placeholder files gracefully
  - Outputs JSONL report with file metadata

**Hash Types**:
- `sha256_hash` - Standard cryptographic hash for exact duplicates
- `image_phash` - Perceptual hash for similar images (via `imagehash`)
- `text_hash` - Text content similarity (via `tlsh`)
- `fuzzy_hash` - Fuzzy hashing for near-duplicates (via `tlsh`)

**Error Handling**:
- Catches `FileNotFoundError`, `OSError`, `PermissionError`
- Skips inaccessible files (OneDrive placeholders, locked files)
- Logs warnings for skipped files

**Cache System**:
- SQLite database: `file_hashes.db`
- Table schema: `(file_path TEXT PRIMARY KEY, file_size INTEGER, modified_time REAL, sha256_hash TEXT, ...)`
- Cache invalidation based on size/mtime changes

#### 2. `drive_organizer.py`
**Purpose**: File organization, tagging, deduplication, and movement operations

**Key Functions**:

**`organize(source, dest, ...)`**:
- Categorizes files by extension/EXIF/custom rules
- Creates destination directory structure
- Optionally preserves source tree structure
- Generates undo logs for all moves

**`tag_files(source, rules_yaml, ...)`**:
- Applies glob patterns from `rules.yaml`
- Assigns multiple tags to files
- Outputs tagged file list as JSONL

**`dedupe(report_path, quarantine, keeper_policy, link_mode, ...)`**:
- Groups files by hash to find duplicates
- Selects keeper file based on policy (newest, largest, alpha, shortestpath)
- Moves/hardlinks/copies duplicates based on link mode
- Creates undo logs for restoration

**`move_by_tags(source, dest, tags_jsonl, require_tags, ...)`**:
- Filters files by required tags
- Moves matching files to destination
- Creates undo logs

**Category System**:
- Default categories: Documents, Images, Audio, Video, Code, Archives, Executables, Miscellaneous
- Customizable via `overrides.json`:
  - `by_extension` - Override category by file extension
  - `by_glob` - Route files matching glob patterns
  - `by_exif` - Route photos by camera model

**Error Handling**:
- `_safe_move()` wrapper catches exceptions
- Skips files that fail to move
- Logs errors without stopping batch operations

#### 3. `duplicates_report.py`
**Purpose**: Generate HTML/CSV reports of duplicate files

**Key Functions**:

**`find_duplicates(report_path, ...)`**:
- Parses JSONL scan report
- Groups files by hash type (sha256, image_phash, text_hash, fuzzy_hash)
- Returns dict mapping hash → list of file paths

**`generate_html_report(duplicates, output_path)`**:
- Creates styled HTML table with duplicate groups
- Shows file paths, sizes, modification times
- Color-codes by hash type

**`generate_csv_report(duplicates, output_path)`**:
- CSV format: `hash_type,hash,file_path,size,modified`
- Suitable for Excel/database import

#### 4. `move_preview_report.py`
**Purpose**: Generate preview reports before executing moves

**Key Functions**:

**`preview_organize(source, dest, ...)`**:
- Simulates organization operation
- Shows source → destination mapping
- Generates HTML/CSV preview without moving files

**`preview_tags(source, dest, tags_jsonl, require_tags, ...)`**:
- Simulates tag-based moves
- Shows which files will be moved based on tag filters

**Error Handling**:
- Catches `FileNotFoundError` for OneDrive files
- Skips inaccessible files during preview

#### 5. `undo_moves.py`
**Purpose**: Reverse file operations using undo logs

**Key Functions**:

**`undo_moves(undo_log_path, dry_run, force_copy_from)`**:
- Parses JSONL undo log
- Reverses moves by moving files back to original locations
- Optionally restores from backup location if files missing
- Supports dry-run mode for safety

**JSONL Log Format**:
```json
{"action": "move", "src": "C:/original/file.txt", "dst": "C:/organized/file.txt", "timestamp": 1699401234.56}
```

### GUI Module

#### `gui_toolkit.py`
**Purpose**: Graphical user interface for all toolkit operations

**Architecture**:
- Class-based design: `DriveCleanupGUI(root)`
- Tab-based interface with 6 tabs
- Threaded command execution to prevent UI blocking
- Menu bar, status bar, and collapsible log panel

**Key Components**:

**Tab Creation Methods**:
- `create_scan_tab()` - File scanning interface
- `create_results_tab()` - Tree view for scan results
- `create_preview_tab()` - Preview report generation
- `create_organize_tab()` - File organization interface
- `create_dedupe_tab()` - Deduplication interface
- `create_undo_tab()` - Undo operations interface

**Results Tab Features**:
- `ttk.Treeview` widget with columns: Path, Size, Modified, Hash, Type
- Sort by column (click headers)
- Context menu: Open File, Open Folder
- Load results from JSONL scan reports
- Filter/search capabilities (planned)

**Threading Model**:
- `run_command_threaded(cmd, callback)` - Runs subprocess in background thread
- Uses `subprocess.Popen` with `stdout=PIPE` for real-time output
- Updates log panel via `self.log()` method
- Updates status bar on completion

**Progress Tracking**:
- `ttk.Progressbar` in scan tab
- Indeterminate mode during operations
- Status messages in status bar

**Menu System**:
- File → Open Report (load JSONL into Results tab)
- File → Exit
- Help → About (messagebox with version info)
- Help → User Guide (opens USER_GUIDE.md in browser)

## Configuration Files

### `overrides.json`
JSON structure for custom categorization:
```json
{
  "by_extension": {
    ".heic": "Images/Phone/HEIC",
    ".md": "Documents/Markdown"
  },
  "by_glob": {
    "**/iPhone/**": "Images/Phone",
    "**/Screenshots/**": "Images/Screenshots"
  },
  "by_exif": {
    "camera_to": {
      "Canon EOS 5D": "Images/RAW/Canon",
      "iPhone 12": "Images/Phone/iPhone12"
    }
  }
}
```

### `rules.yaml`
YAML structure for tagging rules:
```yaml
- name: Work Documents
  include:
    - "**/Work/**"
    - "**/*.docx"
  exclude:
    - "**/_Archive/**"
  tags:
    - work
    - documents

- name: Personal Photos 2024
  include:
    - "**/Photos/2024/**"
  tags:
    - personal
    - photos
    - 2024
```

## Data Formats

### JSONL Scan Report
Each line is a JSON object:
```json
{"path": "C:/file.txt", "size": 1024, "modified": 1699401234.56, "sha256_hash": "abc123...", "extension": ".txt"}
```

### JSONL Undo Log
Each line records a single operation:
```json
{"action": "move", "src": "C:/old/file.txt", "dst": "C:/new/file.txt", "timestamp": 1699401234.56}
```

### JSONL Tagged Files
Each line contains file path and assigned tags:
```json
{"path": "C:/file.txt", "tags": ["work", "documents", "2024"]}
```

## Dependency Map

### Core Python Libraries
- `pathlib` - Path handling
- `hashlib` - SHA-256 hashing
- `json` - JSONL parsing/writing
- `sqlite3` - Hash caching
- `subprocess` - Running commands from GUI
- `threading` - Non-blocking GUI operations

### External Dependencies
- `Pillow` (PIL) - Image processing for EXIF data
- `imagehash` - Perceptual hashing for images
- `pdfminer.six` - PDF text extraction
- `python-docx` - Word document text extraction
- `py-tlsh` - Fuzzy hashing and text similarity

### GUI Dependencies
- `tkinter` (built-in) - GUI framework
- `tkinter.ttk` - Themed widgets (Treeview, Progressbar)

## Installation & Setup

### Requirements
- Python 3.8+ (tested on 3.13.9)
- Virtual environment recommended

### Setup Process
```powershell
# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import PIL, imagehash, pdfminer, docx, tlsh; print('✓ All dependencies installed')"
```

## Error Handling Strategy

### OneDrive Files-On-Demand
**Problem**: OneDrive placeholder files throw `FileNotFoundError` when accessed
**Solution**: Try-except blocks in scanning and organization functions
**Impact**: Gracefully skips inaccessible files with warning logs

### Permission Errors
**Problem**: System files, locked files, or admin-only directories
**Solution**: Catch `PermissionError` and `OSError` during file operations
**Impact**: Continue processing remaining files

### Missing Dependencies
**Problem**: User runs scripts without installing requirements
**Solution**: Import errors caught at module load time
**Impact**: Clear error messages pointing to `pip install -r requirements.txt`

## Performance Optimizations

### Hash Caching
- SQLite database stores computed hashes
- Cache invalidation based on file size + mtime
- Dramatically speeds up re-scans (10x-100x faster)

### Lazy Hashing
- Only computes expensive hashes (perceptual, fuzzy) if requested via flags
- SHA-256 always computed for deduplication
- Text hashing skipped for non-text files

### Threaded GUI
- All subprocess calls run in background threads
- UI remains responsive during long operations
- Real-time output streaming to log panel

## Testing Strategy

### Dry-Run Mode
All destructive operations support `--dry-run` flag:
- Organization: `--dry-run` shows what would be moved
- Deduplication: `--dry-run` shows what would be removed
- Undo: `--dry-run` shows what would be restored

### Preview Reports
Generate HTML/CSV previews before executing:
- Review file movements before committing
- Verify categorization logic
- Check tag-based filtering

### Undo Logs
JSONL logs enable complete rollback:
- Every move operation logged
- `undo_moves.py` reverses all operations
- Supports force-copy from backup location

## Future Enhancements

### Planned Features
- [ ] GUI search/filter in Results tab
- [ ] Batch file selection with checkboxes
- [ ] Custom action buttons in Results tab
- [ ] Real-time progress percentage in scan
- [ ] Pause/resume for long operations
- [ ] Config file editor in GUI
- [ ] Export filtered results to new JSONL

### Performance Improvements
- [ ] Parallel hash computation (multiprocessing)
- [ ] Incremental scanning (only new/changed files)
- [ ] Memory-mapped file hashing for large files

### Additional Hash Algorithms
- [ ] Video perceptual hashing
- [ ] Audio fingerprinting
- [ ] Document similarity (beyond text extraction)

## Troubleshooting

### Common Issues

**ImportError: No module named 'PIL'**
```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**FileNotFoundError during scan**
- OneDrive placeholder files - working as intended, file skipped
- Check if file exists and is accessible

**PermissionError during organization**
- Run PowerShell as Administrator
- Check destination folder permissions
- Ensure files not locked by other programs

**GUI doesn't launch**
- Verify Python installation includes Tkinter
- Check terminal for error messages
- Ensure virtual environment is activated

**Scan report empty**
- Check `--min-size` and `--max-size` filters
- Verify source path is correct
- Check log output for skipped files

