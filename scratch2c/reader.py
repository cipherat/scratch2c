"""
.sb3 file reader.

An .sb3 file is just a ZIP archive. The interesting part is project.json,
which encodes the entire program as a flat dict of block nodes linked by
"next" and "parent" pointers. This module extracts that JSON and returns
it as a plain Python dict — no interpretation yet.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path


def read_sb3(path: str | Path) -> dict:
    """Read a .sb3 file and return the parsed project.json.

    Args:
        path: Path to a .sb3 file (ZIP) or a raw project.json file.

    Returns:
        The parsed JSON as a Python dict.

    Raises:
        FileNotFoundError: if the path doesn't exist.
        ValueError: if the file is neither a valid ZIP nor valid JSON.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")

    # Try as ZIP first (.sb3 is a ZIP)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path, "r") as zf:
            if "project.json" not in zf.namelist():
                raise ValueError(f"{path} is a ZIP but contains no project.json")
            raw = zf.read("project.json")
            return json.loads(raw)

    # Fall back to raw JSON (useful for testing)
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"{path} is neither a valid .sb3 ZIP nor valid JSON: {e}") from e
