"""Tests for the .sb3 / JSON reader."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scratch2c.reader import read_sb3


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestReadSb3:
    """Test the .sb3 file reader."""

    def test_reads_raw_json(self):
        """read_sb3 can read a plain project.json file."""
        result = read_sb3(FIXTURES_DIR / "fibonacci.json")
        assert "targets" in result
        assert len(result["targets"]) == 1

    def test_reads_zip(self, tmp_path):
        """read_sb3 can extract project.json from a ZIP (.sb3) file."""
        project_data = {"targets": [{"name": "Stage", "isStage": True}]}
        sb3_path = tmp_path / "test.sb3"
        with zipfile.ZipFile(sb3_path, "w") as zf:
            zf.writestr("project.json", json.dumps(project_data))

        result = read_sb3(sb3_path)
        assert result["targets"][0]["name"] == "Stage"

    def test_file_not_found(self):
        """read_sb3 raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            read_sb3("/nonexistent/path.sb3")

    def test_invalid_file(self, tmp_path):
        """read_sb3 raises ValueError for files that are neither ZIP nor JSON."""
        bad_file = tmp_path / "garbage.sb3"
        bad_file.write_bytes(b"\x00\x01\x02\x03")
        with pytest.raises(ValueError, match="neither a valid .sb3 ZIP nor valid JSON"):
            read_sb3(bad_file)

    def test_zip_without_project_json(self, tmp_path):
        """read_sb3 raises ValueError for ZIPs missing project.json."""
        sb3_path = tmp_path / "empty.sb3"
        with zipfile.ZipFile(sb3_path, "w") as zf:
            zf.writestr("other.txt", "not a project")
        with pytest.raises(ValueError, match="no project.json"):
            read_sb3(sb3_path)
