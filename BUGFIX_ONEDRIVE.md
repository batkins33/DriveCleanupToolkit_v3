# Bug Fix: OneDrive and File Access Issues

## Problem
The toolkit encountered `FileNotFoundError` when scanning folders containing OneDrive files. This happens with:
- **OneDrive placeholder files** (Files-On-Demand/cloud-only files)
- **Locked files** (in use by other programs)
- **Permission-denied files** (system or protected files)
- **Broken symlinks** or junction points

## Files Fixed

### 1. `move_preview_report.py`
- Added try-except blocks in `preview_organize()` function
- Added try-except blocks in `preview_tags()` function
- Now skips inaccessible files with warning messages

### 2. `scan_storage.py`
- Added error handling when calling `p.stat()`
- Added error handling when hashing files
- Continues scanning even if individual files fail

### 3. `drive_organizer.py`
- Enhanced `_safe_move()` with comprehensive error handling
- Added file existence check in `organize()` function
- Wraps move operations in try-except blocks

## What Changed

**Before:**
```python
size = p.stat().st_size  # ❌ Crashes on inaccessible files
```

**After:**
```python
try:
    size = p.stat().st_size
except (FileNotFoundError, OSError, PermissionError) as e:
    print(f"[WARN] Skipping inaccessible file: {p} ({e})")
    continue
```

## Error Types Handled

- `FileNotFoundError` - File doesn't exist (OneDrive placeholders, deleted files)
- `OSError` - Generic I/O errors (locked files, device errors)
- `PermissionError` - Access denied (system files, protected folders)

## Behavior Now

When the toolkit encounters an inaccessible file:
1. ✅ Prints a warning message with the file path and error
2. ✅ Skips that file and continues processing
3. ✅ Doesn't crash the entire operation
4. ✅ Reports total files successfully processed

## OneDrive-Specific Tips

### Option 1: Make Files Available Offline (Recommended)
Right-click the OneDrive folder → **Always keep on this device**

### Option 2: Skip OneDrive Folders
Use the `--skip-glob` option:
```powershell
python scan_storage.py "C:\Users\YourName" --out "./reports" --skip-glob "*OneDrive*/*"
```

### Option 3: Exclude via .gitignore-style Patterns
In your scan command:
```powershell
--skip-glob "**/OneDrive/**,**/OneDrive - */**"
```

## Testing the Fix

Try running the preview again:
```powershell
python move_preview_report.py --mode organize --source "C:\TestFolder" --dest "C:\Organized" --out preview.html --preserve-tree
```

You should now see warnings instead of crashes:
```
[WARN] Skipping inaccessible file: C:\Users\...\OneDrive\file.pdf (FileNotFoundError)
Report written: preview.html
```

## Additional Safety

All file operations now:
- ✓ Check file existence before processing
- ✓ Handle permission errors gracefully
- ✓ Log warnings for skipped files
- ✓ Continue processing remaining files
- ✓ Report accurate counts of processed files

## Recommendation

When working with OneDrive or network drives:
1. Use `--dry-run` flag first
2. Review the warnings for skipped files
3. Make important files available offline
4. Use `--skip-glob` to exclude problematic paths
5. Run scans on local drives when possible
