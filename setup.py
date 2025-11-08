#!/usr/bin/env python3
"""Setup script for Drive Cleanup Toolkit v3."""

from setuptools import setup
from pathlib import Path

# Read the README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="drive-cleanup-toolkit",
    version="3.0.0",
    description="Comprehensive toolkit for organizing, deduplicating, and managing files on drives",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    python_requires=">=3.8",
    py_modules=[
        "drive_organizer",
        "scan_storage",
        "duplicates_report",
        "move_preview_report",
        "undo_moves",
        "gui_toolkit",
    ],
    install_requires=[
        "Pillow>=10.0.0",
        "imagehash>=4.3.0",
        "pdfminer.six>=20221105",
        "python-docx>=1.0.0",
        "py-tlsh>=4.7.0",
    ],
    entry_points={
        "console_scripts": [
            "drive-organizer=drive_organizer:main",
            "drive-scan=scan_storage:main",
            "drive-duplicates=duplicates_report:main",
            "drive-preview=move_preview_report:main",
            "drive-undo=undo_moves:main",
            "drive-gui=gui_toolkit:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: System :: Filesystems",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
)
