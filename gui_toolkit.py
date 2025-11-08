#!/usr/bin/env python3
# Drive Cleanup Toolkit v3 — Upgraded GUI (CommandRunner + Details Pane + Cancel/Busy + Shortcuts + Prefs)
# This file replaces the previous gui_toolkit.py while preserving CLI contract.
# Created by ChatGPT on 2025-11-07

import os
# Fix Unicode encoding issue on Windows
os.environ['PYTHONIOENCODING'] = 'utf-8'

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import sys
import json
import threading
import queue
from pathlib import Path
import webbrowser
import time
import shlex
import logging

# --- Windows HiDPI hint (no-op elsewhere) ---
try:
    import ctypes  # type: ignore
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Per-monitor aware
    except (AttributeError, OSError):
        pass
except ImportError:
    pass

PY = sys.executable
APP_NAME = "Drive Cleanup Toolkit v3"
PREFS_PATH = Path.home() / ".drive_cleanup_gui.json"

# ---------------------------
# Utilities: prefs, theming, toast
# ---------------------------

def load_prefs():
    try:
        if PREFS_PATH.exists():
            return json.loads(PREFS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        logging.warning(f"Failed to load preferences: {e}")
    return {
        "theme": "dark",
        "geometry": "1280x780",
        "last_tab": 0,
        "last_paths": {}
    }

def save_prefs(prefs):
    try:
        PREFS_PATH.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    except (OSError, UnicodeEncodeError) as e:
        logging.warning(f"Failed to save preferences: {e}")

def show_toast(root, text, duration_ms=2000, theme="dark"):
    # minimal toast in bottom-right
    bg = "#111111" if theme == "dark" else "#333333"
    t = tk.Toplevel(root)
    t.overrideredirect(True)
    t.attributes("-topmost", True)
    t.config(bg=bg)
    label = tk.Label(t, text=text, fg="white", bg=bg, padx=12, pady=8)
    label.pack()
    t.update_idletasks()
    x = root.winfo_rootx() + root.winfo_width() - t.winfo_width() - 24
    y = root.winfo_rooty() + root.winfo_height() - t.winfo_height() - 24
    t.geometry(f"+{x}+{y}")
    t.after(duration_ms, t.destroy)

def apply_theme(root, theme):
    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass

    if theme == "dark":
        bg = "#0f1115"; fg = "#e6e6e6"; panel = "#171a21"; sub = "#a0a8b8"
        entry_bg = "#10131a"; border = "#2a2f3a"; accent = "#3b82f6"
    else:
        bg = "#fafafa"; fg = "#1f2937"; panel = "#ffffff"; sub = "#4b5563"
        entry_bg = "#ffffff"; border = "#e5e7eb"; accent = "#2563eb"

    root.configure(bg=bg)
    s.configure(".", background=bg, foreground=fg)
    s.configure("TFrame", background=bg)
    s.configure("TLabelframe", background=panel, relief="groove", borderwidth=1)
    s.configure("TLabelframe.Label", background=panel, foreground=fg)
    s.configure("TLabel", background=bg, foreground=fg)
    s.configure("TNotebook", background=bg, tabmargins=[8, 6, 8, 0])
    s.configure("TNotebook.Tab", background=panel, foreground=fg, padding=[12, 8], borderwidth=0)
    s.map("TNotebook.Tab", background=[("selected", bg)], foreground=[("selected", fg)])
    s.configure("TEntry", fieldbackground=entry_bg, foreground=fg, insertcolor=fg)
    s.configure("Treeview", background=panel, fieldbackground=panel, foreground=fg, bordercolor=border)
    s.configure("TButton", padding=8)
    s.configure("Accent.TButton", background=accent, foreground="white")
    s.map("Accent.TButton", background=[("active", accent)])
    s.configure("Status.TLabel", background=panel, foreground=sub, padding=6, anchor="w")

# ---------------------------
# CommandRunner: threaded subprocess + queued logs + cancel
# ---------------------------

class CommandRunner:
    def __init__(self, root, on_log, on_done, tick_ms=80):
        self.root = root
        self.on_log = on_log
        self.on_done = on_done
        self.q = queue.Queue()
        self.proc = None
        self._stop = False
        self._tick_ms = tick_ms

    def run(self, args, cwd=None):
        # Validate and sanitize command arguments
        if not args or not isinstance(args, list):
            self.q.put(("__ERROR__", "Invalid command arguments"))
            return
        
        # Validate executable path
        if not Path(args[0]).exists():
            self.q.put(("__ERROR__", f"Executable not found: {args[0]}"))
            return
            
        self._stop = False

        def worker():
            try:
                self.proc = subprocess.Popen(
                    args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1
                )
                if self.proc.stdout is None:
                    self.q.put(("__ERROR__", "Failed to capture process output"))
                    return
                    
                for line in self.proc.stdout:
                    if self._stop:
                        break
                    self.q.put(line.rstrip("\n"))
                code = self.proc.wait()
                self.q.put(("__DONE__", code))
            except (subprocess.SubprocessError, OSError) as e:
                self.q.put(("__ERROR__", str(e)))

        threading.Thread(target=worker, daemon=True).start()
        self._drain()

    def cancel(self):
        self._stop = True
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            except (subprocess.SubprocessError, OSError) as e:
                logging.warning(f"Failed to cancel process: {e}")

    def _drain(self):
        try:
            while True:
                item = self.q.get_nowait()
                if isinstance(item, tuple) and item[0] in ("__DONE__", "__ERROR__"):
                    self.on_done(item)
                else:
                    self.on_log(item)
        except queue.Empty:
            pass
        finally:
            self.root.after(self._tick_ms, self._drain)

# ---------------------------
# Main GUI
# ---------------------------

class DriveCleanupGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)

        self.prefs = load_prefs()
        self.theme = self.prefs.get("theme", "dark")
        apply_theme(root, self.theme)
        self.root.geometry(self.prefs.get("geometry", "1280x780"))

        # Visible focus for keyboard users
        self.root.option_add("*HighlightThickness", 2)
        self.root.option_add("*HighlightColor", "#3b82f6")

        # Menu + toolbar
        self.create_menu()
        self.create_toolbar()

        container = ttk.Frame(root)
        container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Tabs
        self.create_scan_tab()
        self.create_results_tab()
        self.create_preview_tab()
        self.create_organize_tab()
        self.create_dedupe_tab()
        self.create_undo_tab()

        # Status
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(root, textvariable=self.status_var, style="Status.TLabel")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Log
        self.create_log_panel(root)

        # Runner (threaded subprocess)
        self.runner = CommandRunner(
            root=self.root,
            on_log=lambda line: self.log(line),
            on_done=self._on_cmd_done
        )

        # Shortcuts
        self.bind_shortcuts()

        # State updates
        self.update_scan_buttons()
        self.update_preview_buttons()
        self.update_organize_buttons()
        self.update_dedupe_buttons()
        self.update_undo_buttons()

        # Restore last tab
        try:
            last_tab = int(self.prefs.get("last_tab", 0))
            if 0 <= last_tab < self.notebook.index("end"):
                self.notebook.select(last_tab)
        except (ValueError, tk.TclError):
            pass

    # ---------------------------
    # Menu / Toolbar
    # ---------------------------

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Scan Report...  (Ctrl+O)", command=self.open_scan_report)
        file_menu.add_command(label="Export Results CSV   (Ctrl+E)", command=self.export_results)
        file_menu.add_separator()
        file_menu.add_command(label="Exit (Ctrl+Q)", command=self.root.quit)

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Toggle Theme (Light/Dark)", command=self.toggle_theme)
        view_menu.add_command(label="Refresh Results (F5)", command=self.refresh_results)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=lambda: self.open_file("USER_GUIDE.md"))
        help_menu.add_command(label="Quick Reference", command=lambda: self.open_file("QUICKREF.md"))
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.show_about)

    def create_toolbar(self):
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=10, pady=(10, 8))

        ttk.Button(bar, text="▶️ Scan", command=self.focus_scan, style="Accent.TButton").pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="📊 Results", command=lambda: self.notebook.select(1)).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="👁️ Preview", command=lambda: self.notebook.select(2)).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="🗂️ Organize", command=lambda: self.notebook.select(3)).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="🔗 Deduplicate", command=lambda: self.notebook.select(4)).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="↩️ Undo", command=lambda: self.notebook.select(5)).pack(side=tk.LEFT, padx=4)

        ttk.Separator(bar, orient="vertical").pack(side=tk.LEFT, fill="y", padx=8)
        ttk.Button(bar, text="🌗 Theme", command=self.toggle_theme).pack(side=tk.LEFT, padx=4)
        self.cancel_btn = ttk.Button(bar, text="⏹ Cancel", command=self.cancel_current, state="disabled")
        self.cancel_btn.pack(side=tk.LEFT, padx=4)

    def create_log_panel(self, root):
        self.log_frame = ttk.LabelFrame(root, text="Log Output")
        self.log_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, padx=10, pady=(0, 10))
        self.log_frame.pack_propagate(False)

        log_scroll = ttk.Scrollbar(self.log_frame)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(self.log_frame, height=9, wrap=tk.WORD, yscrollcommand=log_scroll.set, bd=0)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.config(command=self.log_text.yview)

    # ---------------------------
    # Tabs
    # ---------------------------

    def create_scan_tab(self):
        scan = ttk.Frame(self.notebook)
        self.notebook.add(scan, text="📁 Scan")

        frm = ttk.Labelframe(scan, text="Scan Configuration", padding=12)
        frm.pack(fill=tk.X, padx=6, pady=8)

        self.s_src = tk.StringVar()
        self.s_out = tk.StringVar()

        self.mk_row(frm, "Source Folder:", self.s_src, self.pick_dir, row=0, pref_key="scan_source")
        self.mk_row(frm, "Output Folder:", self.s_out, self.pick_dir, row=1, pref_key="scan_output")

        opts = ttk.Labelframe(scan, text="Scan Options", padding=12)
        opts.pack(fill=tk.X, padx=6, pady=8)

        self.v_ph = tk.BooleanVar(value=True)
        self.v_tx = tk.BooleanVar(value=False)
        self.v_tl = tk.BooleanVar(value=False)

        ttk.Checkbutton(opts, text="🖼️ Image pHash (near-duplicate images)", variable=self.v_ph).pack(anchor="w", pady=2)
        ttk.Checkbutton(opts, text="📄 Text Hash (similar documents)", variable=self.v_tx).pack(anchor="w", pady=2)
        ttk.Checkbutton(opts, text="🔍 TLSH Fuzzy Hash (advanced near-duplicate)", variable=self.v_tl).pack(anchor="w", pady=2)

        prog = ttk.Frame(scan)
        prog.pack(fill=tk.X, padx=6, pady=4)
        self.scan_progress = ttk.Progressbar(prog, mode="indeterminate")
        self.scan_progress.pack(fill=tk.X)

        btns = ttk.Frame(scan)
        btns.pack(fill=tk.X, padx=6, pady=8)
        self.btn_scan = ttk.Button(btns, text="▶️ Run Scan", command=self.run_scan, style="Accent.TButton")
        self.btn_scan.pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="📊 View Results", command=self.view_scan_results).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="📂 Open Output Folder", command=self.open_output_folder).pack(side=tk.LEFT, padx=4)

        ttk.Label(scan, text="Output includes: scan_report.jsonl, duplicates.csv, near_dupes.csv, hash_cache.sqlite3",
                  foreground="#7a869a").pack(pady=(0, 6))

        self.s_src.trace_add("write", lambda *_: self.update_scan_buttons())
        self.s_out.trace_add("write", lambda *_: self.update_scan_buttons())

    def create_results_tab(self):
        results = ttk.Frame(self.notebook)
        self.notebook.add(results, text="📊 Results")

        toolbar = ttk.Frame(results)
        toolbar.pack(fill=tk.X, padx=6, pady=(6, 2))

        ttk.Button(toolbar, text="📂 Load Report (Ctrl+O)", command=self.load_report).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🔄 Refresh (F5)", command=self.refresh_results).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="💾 Export CSV (Ctrl+E)", command=self.export_results).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=8, fill=tk.Y)

        ttk.Label(toolbar, text="Filter:").pack(side=tk.LEFT, padx=(4, 2))
        self.filter_var = tk.StringVar()
        ent = ttk.Entry(toolbar, textvariable=self.filter_var, width=32)
        ent.pack(side=tk.LEFT, padx=(0, 8))
        self.filter_var.trace_add("write", lambda *_: self.apply_filter())

        split = ttk.Panedwindow(results, orient="horizontal")
        split.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        left = ttk.Frame(split)
        right = ttk.Labelframe(split, text="Details", padding=10)
        split.add(left, weight=3)
        split.add(right, weight=2)

        stats_frame = ttk.Labelframe(left, text="Summary", padding=10)
        stats_frame.pack(fill=tk.X, padx=2, pady=(0, 6))
        self.stats_text = tk.StringVar(value="No data loaded. Click 'Load Report' to view scan results.")
        ttk.Label(stats_frame, textvariable=self.stats_text, justify="left").pack(anchor="w")

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        yscroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        xscroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        xscroll.pack(side=tk.BOTTOM, fill=tk.X)

        columns = ("path", "size", "modified", "sha256", "duplicates")
        self.results_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            yscrollcommand=yscroll.set,
            xscrollcommand=xscroll.set,
            selectmode="browse"
        )
        self.results_tree.heading("path", text="File Path", command=lambda: self.sort_column("path", False))
        self.results_tree.heading("size", text="Size", command=lambda: self.sort_column("size", False))
        self.results_tree.heading("modified", text="Modified", command=lambda: self.sort_column("modified", False))
        self.results_tree.heading("sha256", text="SHA-256", command=lambda: self.sort_column("sha256", False))
        self.results_tree.heading("duplicates", text="Dup Count", command=lambda: self.sort_column("duplicates", False))

        self.results_tree.column("path", width=520)
        self.results_tree.column("size", width=110, anchor="e")
        self.results_tree.column("modified", width=160)
        self.results_tree.column("sha256", width=220)
        self.results_tree.column("duplicates", width=90, anchor="center")

        self.results_tree.pack(fill=tk.BOTH, expand=True)
        yscroll.config(command=self.results_tree.yview)
        xscroll.config(command=self.results_tree.xview)

        self.results_tree.bind("<<TreeviewSelect>>", self.on_row_select)
        self.results_tree.bind("<Double-1>", self.open_selected_file)
        self.results_tree.bind("<Button-3>", self.show_context_menu)

        # Details panel
        self.detail_vars = {
            "path": tk.StringVar(value="—"),
            "size": tk.StringVar(value="—"),
            "modified": tk.StringVar(value="—"),
            "sha256": tk.StringVar(value="—"),
            "dup_count": tk.StringVar(value="—")
        }

        def row(label, key):
            r = ttk.Frame(right)
            r.pack(fill=tk.X, pady=4)
            ttk.Label(r, text=label, width=12).pack(side=tk.LEFT)
            ttk.Label(r, textvariable=self.detail_vars[key], wraplength=420, justify="left").pack(side=tk.LEFT, fill=tk.X, expand=True)

        row("Path:", "path")
        row("Size:", "size")
        row("Modified:", "modified")
        row("SHA-256:", "sha256")
        row("Dup count:", "dup_count")

        action_bar = ttk.Frame(right)
        action_bar.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(action_bar, text="Open File", command=self.open_selected_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(action_bar, text="Open Folder", command=self.open_containing_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(action_bar, text="Copy Path", command=self.copy_path).pack(side=tk.LEFT, padx=4)

        self.current_data = []

    def create_preview_tab(self):
        prev = ttk.Frame(self.notebook)
        self.notebook.add(prev, text="👁️ Preview")

        cfg = ttk.Labelframe(prev, text="Preview Configuration", padding=12)
        cfg.pack(fill=tk.X, padx=6, pady=8)

        self.preview_mode = tk.StringVar(value="organize")
        modes = ttk.Frame(cfg)
        modes.pack(fill=tk.X, pady=(0, 6))
        ttk.Radiobutton(modes, text="Organize by Category", variable=self.preview_mode, value="organize").pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(modes, text="Move by Tags", variable=self.preview_mode, value="tags").pack(side=tk.LEFT, padx=6)

        grid = ttk.Frame(cfg)
        grid.pack(fill=tk.X, pady=4)
        self.p_src = tk.StringVar(); self.p_dst = tk.StringVar()
        self.p_tagsj = tk.StringVar(); self.p_tags = tk.StringVar()
        self.p_over = tk.StringVar(); self.p_out = tk.StringVar()
        self.p_pres = tk.BooleanVar(value=True)

        self.mk_row(grid, "Source:", self.p_src, self.pick_dir, row=0, pref_key="preview_source")
        self.mk_row(grid, "Destination:", self.p_dst, self.pick_dir, row=1, pref_key="preview_dest")
        self.mk_row(grid, "Tags JSONL:", self.p_tagsj, self.pick_file, row=2, pref_key="preview_tagsj")
        self.mk_row(grid, "Overrides JSON:", self.p_over, self.pick_file, row=3, pref_key="preview_overrides")
        self.mk_row(grid, "Output HTML:", self.p_out, lambda v=self.p_out: self.pick_save_file(v, "html"), row=4, pref_key="preview_out")

        ttk.Label(cfg, text="Tags (comma):").pack(anchor="w")
        ttk.Entry(cfg, textvariable=self.p_tags, width=60).pack(fill=tk.X, padx=2, pady=(0, 6))
        ttk.Checkbutton(cfg, text="Preserve directory tree", variable=self.p_pres).pack(anchor="w", pady=4)

        bar = ttk.Frame(prev)
        bar.pack(fill=tk.X, padx=6, pady=8)
        self.btn_prev = ttk.Button(bar, text="▶️ Generate Preview", command=self.run_preview, style="Accent.TButton")
        self.btn_prev.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="🌐 Open in Browser", command=self.open_preview_html).pack(side=tk.LEFT, padx=4)

        for v in (self.p_src, self.p_dst, self.p_out, self.p_tagsj, self.p_tags, self.p_over):
            v.trace_add("write", lambda *_: self.update_preview_buttons())
        self.preview_mode.trace_add("write", lambda *_: self.update_preview_buttons())

    def create_organize_tab(self):
        org = ttk.Frame(self.notebook)
        self.notebook.add(org, text="🗂️ Organize")

        cfg = ttk.Labelframe(org, text="Organization Settings", padding=12)
        cfg.pack(fill=tk.X, padx=6, pady=8)

        self.o_src = tk.StringVar(); self.o_dst = tk.StringVar(); self.o_over = tk.StringVar()
        self.o_pres = tk.BooleanVar(value=True); self.o_dry = tk.BooleanVar(value=True)

        self.mk_row(cfg, "Source Folder:", self.o_src, self.pick_dir, row=0, pref_key="org_source")
        self.mk_row(cfg, "Destination Folder:", self.o_dst, self.pick_dir, row=1, pref_key="org_dest")
        self.mk_row(cfg, "Overrides JSON:", self.o_over, self.pick_file, row=2, pref_key="org_overrides")

        toggles = ttk.Frame(cfg); toggles.grid(row=3, column=1, sticky="w", pady=6)
        ttk.Checkbutton(toggles, text="Preserve directory tree", variable=self.o_pres).pack(anchor="w")
        ttk.Checkbutton(toggles, text="🛡️ DRY RUN (preview only, no changes)", variable=self.o_dry).pack(anchor="w")

        warn = ttk.Label(org, text="⚠️ Always run in DRY RUN first. Uncheck only after reviewing the preview output.",
                         foreground="#e11d48")
        warn.pack(fill=tk.X, padx=8, pady=(2, 6))

        bar = ttk.Frame(org); bar.pack(fill=tk.X, padx=6, pady=8)
        self.btn_org = ttk.Button(bar, text="▶️ Run Organize", command=self.run_organize, style="Accent.TButton")
        self.btn_org.pack(side=tk.LEFT, padx=4)

        for v in (self.o_src, self.o_dst, self.o_over):
            v.trace_add("write", lambda *_: self.update_organize_buttons())

    def create_dedupe_tab(self):
        ded = ttk.Frame(self.notebook)
        self.notebook.add(ded, text="🔗 Deduplicate")

        cfg = ttk.Labelframe(ded, text="Deduplication Settings", padding=12)
        cfg.pack(fill=tk.X, padx=6, pady=8)

        self.d_rep = tk.StringVar(); self.d_qua = tk.StringVar()
        self.d_keep = tk.StringVar(value="newest")
        self.d_mode = tk.StringVar(value="move")
        self.d_dry = tk.BooleanVar(value=True)

        self.mk_row(cfg, "Scan Report (JSONL):", self.d_rep, self.pick_file, row=0, pref_key="ded_report")
        self.mk_row(cfg, "Quarantine Folder:", self.d_qua, self.pick_dir, row=1, pref_key="ded_quarantine")

        ttk.Label(cfg, text="Keeper Policy:").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Combobox(cfg, textvariable=self.d_keep, width=20,
                     values=["newest", "largest", "alpha", "shortestpath"], state="readonly").grid(row=2, column=1, sticky="w", padx=2)

        ttk.Label(cfg, text="Dedup Mode:").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Combobox(cfg, textvariable=self.d_mode, width=20,
                     values=["move", "hardlink", "copy"], state="readonly").grid(row=3, column=1, sticky="w", padx=2)

        ttk.Checkbutton(cfg, text="🛡️ DRY RUN (preview only)", variable=self.d_dry).grid(row=4, column=1, sticky="w", pady=5)

        info = ttk.Labelframe(ded, text="Mode Explanations", padding=10)
        info.pack(fill=tk.X, padx=6, pady=6)
        ttk.Label(info, text="• move: move duplicates to quarantine (safest)\n• hardlink: replace dups with hard links (space saver)\n• copy: replace dups with copies of keeper").pack(anchor="w")

        bar = ttk.Frame(ded); bar.pack(fill=tk.X, padx=6, pady=8)
        self.btn_ded = ttk.Button(bar, text="▶️ Run Deduplication", command=self.run_dedupe, style="Accent.TButton")
        self.btn_ded.pack(side=tk.LEFT, padx=4)

        for v in (self.d_rep, self.d_qua, self.d_keep, self.d_mode):
            v.trace_add("write", lambda *_: self.update_dedupe_buttons())

    def create_undo_tab(self):
        un = ttk.Frame(self.notebook)
        self.notebook.add(un, text="↩️ Undo")

        cfg = ttk.Labelframe(un, text="Undo Configuration", padding=12)
        cfg.pack(fill=tk.X, padx=6, pady=8)

        self.u_log = tk.StringVar(); self.u_bak = tk.StringVar(); self.u_dry = tk.BooleanVar(value=True)

        self.mk_row(cfg, "Undo Log (JSONL):", self.u_log, self.pick_file, row=0, pref_key="undo_log")
        self.mk_row(cfg, "Backup Folder (optional):", self.u_bak, self.pick_dir, row=1, pref_key="undo_backup")
        ttk.Checkbutton(cfg, text="🛡️ DRY RUN (preview only)", variable=self.u_dry).grid(row=2, column=1, sticky="w", pady=5)

        info = ttk.Labelframe(un, text="Information", padding=10)
        info.pack(fill=tk.X, padx=6, pady=6)
        ttk.Label(info, text="Undo will reverse operations recorded in the undo log.\nFor hardlink/copy operations, provide a backup folder to restore originals.",
                  wraplength=800, justify="left").pack(anchor="w")

        bar = ttk.Frame(un); bar.pack(fill=tk.X, padx=6, pady=8)
        self.btn_undo = ttk.Button(bar, text="▶️ Run Undo", command=self.run_undo, style="Accent.TButton")
        self.btn_undo.pack(side=tk.LEFT, padx=4)

        for v in (self.u_log, self.u_bak):
            v.trace_add("write", lambda *_: self.update_undo_buttons())

    # ---------------------------
    # Shared widgets / helpers
    # ---------------------------

    def mk_row(self, parent, label, var, picker, row=0, pref_key=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        e = ttk.Entry(parent, textvariable=var, width=62)
        e.grid(row=row, column=1, padx=5, sticky="we")
        ttk.Button(parent, text="Browse...", command=lambda v=var, k=pref_key: self._pick_and_persist(v, picker, k)).grid(row=row, column=2, padx=2)

        # load last path if empty
        if pref_key and not var.get():
            last = self.prefs.get("last_paths", {}).get(pref_key)
            if last:
                var.set(last)

    def _pick_and_persist(self, var, picker, pref_key):
        before = var.get()
        picker(var)
        after = var.get()
        if pref_key and after and after != before:
            lp = self.prefs.setdefault("last_paths", {})
            lp[pref_key] = after
            save_prefs(self.prefs)

    def pick_dir(self, var):
        initial = self._initial_for(var)
        d = filedialog.askdirectory(initialdir=initial) if initial else filedialog.askdirectory()
        if d:
            var.set(d)

    def pick_file(self, var):
        initial = self._initial_for(var)
        f = filedialog.askopenfilename(initialdir=initial) if initial else filedialog.askopenfilename()
        if f:
            var.set(f)

    def _initial_for(self, var):
        # pick a sensible initial dir from the current value or prefs
        val = var.get().strip()
        if val:
            try:
                p = Path(val).resolve()  # Resolve to prevent path traversal
                if p.is_dir():
                    return str(p)
                elif p.parent.exists():
                    return str(p.parent)
            except (OSError, ValueError):
                pass
        return None

    def pick_save_file(self, var, ext):
        f = filedialog.asksaveasfilename(defaultextension=f".{ext}", filetypes=[(f"{ext.upper()} files", f"*.{ext}")])
        if f:
            var.set(f)

    def open_file(self, filename):
        try:
            # Validate and sanitize file path
            safe_path = Path(filename).resolve()
            if not safe_path.exists():
                messagebox.showerror("Error", f"File not found: {filename}")
                return
            os.startfile(str(safe_path))
        except (OSError, ValueError) as e:
            try:
                webbrowser.open(f"file://{safe_path.as_uri()}")
            except Exception:
                messagebox.showerror("Error", f"Could not open file: {e}")

    def show_about(self):
        messagebox.showinfo("About", f"{APP_NAME}\n\nA comprehensive file organization and deduplication tool.\n© 2025")

    def log(self, message):
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def set_status(self, message):
        self.status_var.set(message)
        self.root.update_idletasks()

    # ---------------------------
    # Busy / Cancel
    # ---------------------------

    def set_busy(self, is_busy: bool, label="Working…"):
        targets = [getattr(self, n) for n in ("btn_scan","btn_prev","btn_org","btn_ded","btn_undo") if hasattr(self, n)]
        for b in targets:
            b.config(state=("disabled" if is_busy else "normal"))
        if is_busy:
            self.status_var.set(label)
            self.scan_progress.start()
            self.cancel_btn.config(state="normal")
        else:
            self.scan_progress.stop()
            self.cancel_btn.config(state="disabled")

    def cancel_current(self):
        self.runner.cancel()
        self.set_busy(False, label="Canceled")
        show_toast(self.root, "Canceled", theme=self.theme)

    # ---------------------------
    # Commands (use CommandRunner)
    # ---------------------------

    def run_scan(self):
        if not self.s_src.get() or not self.s_out.get():
            messagebox.showerror("Error", "Please specify source and output folders")
            return
        
        # Validate paths
        try:
            src_path = Path(self.s_src.get()).resolve()
            out_path = Path(self.s_out.get()).resolve()
            if not src_path.exists():
                messagebox.showerror("Error", f"Source folder does not exist: {src_path}")
                return
        except (OSError, ValueError) as e:
            messagebox.showerror("Error", f"Invalid path: {e}")
            return
            
        cmd = [PY, "scan_storage.py", str(src_path), "--out", str(out_path)]
        if self.v_ph.get(): cmd.append("--image-phash")
        if self.v_tx.get(): cmd.append("--text-hash")
        if self.v_tl.get(): cmd.append("--fuzzy")
        self.set_busy(True, label="Scanning…")
        self.runner.run(cmd)

    def run_preview(self):
        if not self.p_src.get() or not self.p_dst.get() or not self.p_out.get():
            messagebox.showerror("Error", "Please specify source, destination, and output file")
            return
        
        # Validate paths
        try:
            src_path = Path(self.p_src.get()).resolve()
            dst_path = Path(self.p_dst.get()).resolve()
            out_path = Path(self.p_out.get()).resolve()
        except (OSError, ValueError) as e:
            messagebox.showerror("Error", f"Invalid path: {e}")
            return
            
        cmd = [PY, "move_preview_report.py", "--mode", self.preview_mode.get(),
               "--source", str(src_path), "--dest", str(dst_path), "--out", str(out_path)]
        if self.preview_mode.get() == "tags":
            if not self.p_tagsj.get() or not self.p_tags.get():
                messagebox.showerror("Error", "Tags mode requires Tags JSONL and comma tag list")
                return
            try:
                tags_path = Path(self.p_tagsj.get()).resolve()
                cmd.extend(["--tags-jsonl", str(tags_path), "--require-tags", self.p_tags.get()])
            except (OSError, ValueError) as e:
                messagebox.showerror("Error", f"Invalid tags file path: {e}")
                return
        else:
            if self.p_over.get():
                try:
                    over_path = Path(self.p_over.get()).resolve()
                    cmd.extend(["--category-overrides", str(over_path)])
                except (OSError, ValueError) as e:
                    messagebox.showerror("Error", f"Invalid overrides file path: {e}")
                    return
            if self.p_pres.get():
                cmd.append("--preserve-tree")
        self.set_busy(True, label="Generating preview…")
        self.runner.run(cmd)

    def run_organize(self):
        if not self.o_src.get() or not self.o_dst.get():
            messagebox.showerror("Error", "Please specify source and destination folders")
            return
        if messagebox.askyesno("Confirm", "Proceed with organizing? Run DRY RUN first to preview.") is False:
            return
        
        # Validate paths
        try:
            src_path = Path(self.o_src.get()).resolve()
            dst_path = Path(self.o_dst.get()).resolve()
        except (OSError, ValueError) as e:
            messagebox.showerror("Error", f"Invalid path: {e}")
            return
            
        cmd = [PY, "drive_organizer.py", "organize", "--source", str(src_path), "--dest", str(dst_path)]
        if self.o_over.get():
            try:
                over_path = Path(self.o_over.get()).resolve()
                cmd.extend(["--category-overrides", str(over_path)])
            except (OSError, ValueError) as e:
                messagebox.showerror("Error", f"Invalid overrides file path: {e}")
                return
        if self.o_pres.get(): cmd.append("--preserve-tree")
        if self.o_dry.get(): cmd.append("--dry-run")
        self.set_busy(True, label="Organizing…")
        self.runner.run(cmd)

    def run_dedupe(self):
        if not self.d_rep.get() or not self.d_qua.get():
            messagebox.showerror("Error", "Please specify scan report and quarantine folder")
            return
        if messagebox.askyesno("Confirm", "Proceed with deduplication? DRY RUN is recommended.") is False:
            return
        
        # Validate paths
        try:
            rep_path = Path(self.d_rep.get()).resolve()
            qua_path = Path(self.d_qua.get()).resolve()
            if not rep_path.exists():
                messagebox.showerror("Error", f"Report file does not exist: {rep_path}")
                return
        except (OSError, ValueError) as e:
            messagebox.showerror("Error", f"Invalid path: {e}")
            return
            
        cmd = [PY, "drive_organizer.py", "dedupe", "--report", str(rep_path),
               "--quarantine", str(qua_path), "--keeper", self.d_keep.get(),
               "--link-mode", self.d_mode.get()]
        if self.d_dry.get(): cmd.append("--dry-run")
        self.set_busy(True, label="Deduplicating…")
        self.runner.run(cmd)

    def run_undo(self):
        if not self.u_log.get():
            messagebox.showerror("Error", "Please specify undo log file")
            return
        
        # Validate paths
        try:
            log_path = Path(self.u_log.get()).resolve()
            if not log_path.exists():
                messagebox.showerror("Error", f"Undo log file does not exist: {log_path}")
                return
        except (OSError, ValueError) as e:
            messagebox.showerror("Error", f"Invalid log file path: {e}")
            return
            
        cmd = [PY, "undo_moves.py", "--log", str(log_path)]
        if self.u_bak.get():
            try:
                bak_path = Path(self.u_bak.get()).resolve()
                cmd.extend(["--force-copy-from", str(bak_path)])
            except (OSError, ValueError) as e:
                messagebox.showerror("Error", f"Invalid backup path: {e}")
                return
        if self.u_dry.get(): cmd.append("--dry-run")
        self.set_busy(True, label="Undoing…")
        self.runner.run(cmd)

    # ---------------------------
    # Command completion
    # ---------------------------

    def _on_cmd_done(self, result):
        tag, val = result
        self.set_busy(False)
        if tag == "__DONE__":
            if val == 0:
                show_toast(self.root, "Completed", theme=self.theme)
                self.set_status("✓ Completed")
                # On successful scan, try to autoload latest report
                self.auto_load_latest_report()
            else:
                self.set_status(f"Failed (exit {val})")
                messagebox.showwarning("Finished with errors", f"Exit code: {val}")
        else:
            messagebox.showerror("Error", val)
            self.set_status("Error")

    # ---------------------------
    # Results helpers
    # ---------------------------

    def load_report(self):
        file = filedialog.askopenfilename(filetypes=[("JSONL files", "*.jsonl"), ("All files", "*.*")])
        if file:
            self.load_report_file(file)

    def load_report_file(self, filepath):
        try:
            # Validate and sanitize file path
            safe_path = Path(filepath).resolve()
            if not safe_path.exists():
                messagebox.showerror("Error", f"Report file not found: {filepath}")
                return
                
            self.set_status(f"Loading {safe_path.name}...")
            self.current_data = []
            dup_map = {}
            with open(safe_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        rec = json.loads(line)
                        self.current_data.append(rec)
                        sha = rec.get("sha256")
                        if sha:
                            dup_map.setdefault(sha, []).append(rec)

            # clear tree
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)

            total_size = 0
            dup_count = 0

            for rec in self.current_data:
                path = rec.get("path", "")
                size = rec.get("size_human", "")
                mtime = rec.get("mtime", "")[:19] if rec.get("mtime") else ""
                sha = rec.get("sha256", "")
                sha_short = (sha[:16] + "...") if sha else ""
                dup_cnt = len(dup_map.get(sha, [])) if sha else 1
                if dup_cnt > 1:
                    dup_count += 1
                total_size += rec.get("size", 0)
                self.results_tree.insert("", "end", values=(path, size, mtime, sha_short, dup_cnt if dup_cnt > 1 else ""))

            file_count = len(self.current_data)
            dup_groups = sum(1 for v in dup_map.values() if len(v) > 1)
            stats = f"Files: {file_count:,} | Total Size: {self.human_size(total_size)} | Duplicates: {dup_count:,} ({dup_groups} groups)"
            self.stats_text.set(stats)
            self.set_status(f"Loaded {file_count:,} files")
            show_toast(self.root, "Report loaded", theme=self.theme)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            messagebox.showerror("Error", f"Failed to load report: {e}")
            self.set_status("Error loading report")

    def on_row_select(self, _evt=None):
        sel = self.results_tree.selection()
        if not sel:
            return
        vals = self.results_tree.item(sel[0])["values"]
        self.detail_vars["path"].set(vals[0])
        self.detail_vars["size"].set(vals[1])
        self.detail_vars["modified"].set(vals[2])
        self.detail_vars["sha256"].set(vals[3])
        self.detail_vars["dup_count"].set(vals[4] if vals[4] else "—")

    def auto_load_latest_report(self):
        # Try output path first; fallback to scan tab's out dir
        out_candidates = []
        if self.s_out.get():
            out_candidates.append(Path(self.s_out.get()))
        # Try last known preview/organize locations (in case report saved there)
        for key in ("scan_output",):
            lp = self.prefs.get("last_paths", {}).get(key)
            if lp:
                out_candidates.append(Path(lp))

        for out in out_candidates:
            p = out / "scan_report.jsonl"
            if p.exists():
                self.load_report_file(str(p))
                self.notebook.select(1)
                break

    def refresh_results(self, *_):
        self.auto_load_latest_report()

    def export_results(self):
        if not getattr(self, "current_data", None):
            messagebox.showinfo("Info", "No data to export")
            return
        file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if file:
            try:
                import csv
                safe_path = Path(file).resolve()
                with open(safe_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=self.current_data[0].keys())
                    writer.writeheader()
                    writer.writerows(self.current_data)
                messagebox.showinfo("Success", f"Exported {len(self.current_data)} rows to {safe_path.name}")
            except (OSError, UnicodeEncodeError, csv.Error) as e:
                messagebox.showerror("Error", f"Export failed: {e}")

    def apply_filter(self):
        text = self.filter_var.get().lower()
        for item in self.results_tree.get_children():
            vals = self.results_tree.item(item)["values"]
            match = any(text in str(v).lower() for v in vals)
            self.results_tree.item(item, tags=(() if match else ("hidden",)))
        self.results_tree.tag_configure("hidden", foreground="#7a869a")

    def sort_column(self, col, reverse):
        items = [(self.results_tree.set(k, col), k) for k in self.results_tree.get_children("")]
        items.sort(reverse=reverse)
        for idx, (_val, k) in enumerate(items):
            self.results_tree.move(k, "", idx)
        self.results_tree.heading(col, command=lambda: self.sort_column(col, not reverse))

    def show_context_menu(self, event):
        item = self.results_tree.identify_row(event.y)
        if item:
            self.results_tree.selection_set(item)
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Open File", command=self.open_selected_file)
            menu.add_command(label="Open Containing Folder", command=self.open_containing_folder)
            menu.add_command(label="Copy Path", command=self.copy_path)
            menu.post(event.x_root, event.y_root)

    def open_selected_file(self, event=None):
        sel = self.results_tree.selection()
        if sel:
            path = self.results_tree.item(sel[0])["values"][0]
            try:
                safe_path = Path(path).resolve()
                if not safe_path.exists():
                    messagebox.showerror("Error", f"File not found: {path}")
                    return
                os.startfile(str(safe_path))
            except (OSError, ValueError) as e:
                messagebox.showerror("Error", f"Could not open: {e}")

    def open_containing_folder(self):
        sel = self.results_tree.selection()
        if sel:
            path = self.results_tree.item(sel[0])["values"][0]
            try:
                safe_path = Path(path).resolve()
                folder = safe_path.parent
                if not folder.exists():
                    messagebox.showerror("Error", f"Folder not found: {folder}")
                    return
                os.startfile(str(folder))
            except (OSError, ValueError) as e:
                messagebox.showerror("Error", f"Could not open folder: {e}")

    def copy_path(self):
        sel = self.results_tree.selection()
        if sel:
            path = self.results_tree.item(sel[0])["values"][0]
            self.root.clipboard_clear()
            self.root.clipboard_append(path)
            self.set_status(f"Copied: {path}")
            show_toast(self.root, "Path copied", theme=self.theme)

    def view_scan_results(self):
        self.notebook.select(1)
        self.auto_load_latest_report()

    def open_output_folder(self):
        if self.s_out.get():
            try:
                safe_path = Path(self.s_out.get()).resolve()
                if not safe_path.exists():
                    messagebox.showerror("Error", f"Folder not found: {self.s_out.get()}")
                    return
                os.startfile(str(safe_path))
            except (OSError, ValueError) as e:
                messagebox.showerror("Error", f"Could not open folder: {e}")

    def open_preview_html(self):
        if self.p_out.get():
            try:
                safe_path = Path(self.p_out.get()).resolve()
                if safe_path.exists():
                    webbrowser.open(safe_path.as_uri())
                else:
                    messagebox.showwarning("Warning", "Preview file not found. Generate it first.")
            except (OSError, ValueError) as e:
                messagebox.showerror("Error", f"Invalid file path: {e}")
        else:
            messagebox.showwarning("Warning", "No preview file specified.")

    def open_scan_report(self):
        file = filedialog.askopenfilename(title="Open Scan Report",
            filetypes=[("JSONL files", "*.jsonl"), ("All files", "*.*")])
        if file:
            self.load_report_file(file)
            self.notebook.select(1)

    @staticmethod
    def human_size(bytes_):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_ < 1024.0:
                return f"{bytes_:.2f} {unit}"
            bytes_ /= 1024.0
        return f"{bytes_:.2f} PB"

    # ---------------------------
    # State / validation
    # ---------------------------

    def update_scan_buttons(self):
        ok = bool(self.s_src.get() and self.s_out.get())
        self.btn_scan.config(state=("normal" if ok else "disabled"))

    def update_preview_buttons(self):
        mode = self.preview_mode.get()
        base_ok = bool(self.p_src.get() and self.p_dst.get() and self.p_out.get())
        if mode == "tags":
            ok = base_ok and bool(self.p_tagsj.get() and self.p_tags.get())
        else:
            ok = base_ok
        self.btn_prev.config(state=("normal" if ok else "disabled"))

    def update_organize_buttons(self):
        ok = bool(self.o_src.get() and self.o_dst.get())
        self.btn_org.config(state=("normal" if ok else "disabled"))

    def update_dedupe_buttons(self):
        ok = bool(self.d_rep.get() and self.d_qua.get())
        self.btn_ded.config(state=("normal" if ok else "disabled"))

    def update_undo_buttons(self):
        ok = bool(self.u_log.get())
        self.btn_undo.config(state=("normal" if ok else "disabled"))

    # ---------------------------
    # Theme / shortcuts / lifecycle
    # ---------------------------

    def toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        self.prefs["theme"] = self.theme
        save_prefs(self.prefs)
        apply_theme(self.root, self.theme)
        show_toast(self.root, f"Theme: {self.theme.capitalize()}", theme=self.theme)

    def bind_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self.open_scan_report())
        self.root.bind("<Control-e>", lambda e: self.export_results())
        self.root.bind("<Control-q>", lambda e: self.root.quit())
        self.root.bind("<F5>", self.refresh_results)
        self.root.bind("<Control-Return>", lambda e: self.run_scan())
        self.root.bind("<Control-p>", lambda e: self.run_preview())
        self.root.bind("<Escape>", lambda e: self.cancel_current())

    def _on_tab_changed(self, _evt=None):
        idx = self.notebook.index(self.notebook.select())
        self.prefs["last_tab"] = idx
        save_prefs(self.prefs)

    def on_close(self):
        try:
            self.prefs["geometry"] = self.root.winfo_geometry()
            save_prefs(self.prefs)
        except tk.TclError:
            pass
        self.root.destroy()

    def focus_scan(self):
        self.notebook.select(0)

def main():
    root = tk.Tk()
    app = DriveCleanupGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()