"""Tests for renamer.py"""

import subprocess
import sys
from pathlib import Path

import pytest

from renamer import rename_files


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_files(directory: Path, *names: str) -> None:
    for name in names:
        (directory / name).touch()


def run_cli(*args: str):
    """Run renamer.py as a subprocess and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "renamer.py", *args],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# Argument validation (CLI)
# ---------------------------------------------------------------------------

class TestArgumentValidation:
    def test_missing_dir_exits_nonzero(self):
        code, _, _ = run_cli("--pattern", "foo")
        assert code != 0

    def test_missing_pattern_exits_nonzero(self):
        code, _, _ = run_cli("--dir", ".")
        assert code != 0

    def test_nonexistent_dir_exits_1(self, tmp_path):
        code, _, stderr = run_cli("--dir", str(tmp_path / "no_such_dir"), "--pattern", "foo")
        assert code == 1
        assert "not a directory" in stderr.lower() or "error" in stderr.lower()


# ---------------------------------------------------------------------------
# Basic renaming
# ---------------------------------------------------------------------------

class TestBasicRenaming:
    def test_renames_matching_files(self, tmp_path):
        make_files(tmp_path, "foo_bar.txt", "baz_qux.txt", "unchanged.txt")
        rename_files(str(tmp_path), "_", "-", recursive=False)
        assert (tmp_path / "foo-bar.txt").exists()
        assert (tmp_path / "baz-qux.txt").exists()

    def test_leaves_non_matching_files_untouched(self, tmp_path):
        make_files(tmp_path, "foo_bar.txt", "unchanged.txt")
        rename_files(str(tmp_path), "^NOMATCH", "x", recursive=False)
        assert (tmp_path / "foo_bar.txt").exists()
        assert (tmp_path / "unchanged.txt").exists()

    def test_deletes_matched_portion_when_replacement_is_empty(self, tmp_path):
        make_files(tmp_path, "foo_bar.txt")
        rename_files(str(tmp_path), "_bar", "", recursive=False)
        assert (tmp_path / "foo.txt").exists()
        assert not (tmp_path / "foo_bar.txt").exists()

    def test_returns_count_of_renamed_entries(self, tmp_path, capsys):
        make_files(tmp_path, "foo_bar.txt", "baz_qux.txt", "unchanged.txt")
        rename_files(str(tmp_path), "_", "-", recursive=False)
        out = capsys.readouterr().out
        assert "2 entry(ies) renamed" in out


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_does_not_rename_files(self, tmp_path):
        make_files(tmp_path, "old_name.txt")
        rename_files(str(tmp_path), "old_name", "new_name", recursive=False, dry_run=True)
        assert (tmp_path / "old_name.txt").exists()
        assert not (tmp_path / "new_name.txt").exists()

    def test_reports_would_be_renamed_count(self, tmp_path, capsys):
        make_files(tmp_path, "old_name.txt")
        rename_files(str(tmp_path), "old_name", "new_name", recursive=False, dry_run=True)
        out = capsys.readouterr().out
        assert "1 entry(ies) would be renamed" in out


# ---------------------------------------------------------------------------
# Collision detection
# ---------------------------------------------------------------------------

class TestCollisionDetection:
    def test_skips_rename_when_destination_exists(self, tmp_path):
        make_files(tmp_path, "foo.txt", "bar.txt")
        rename_files(str(tmp_path), "^foo", "bar", recursive=False)
        assert (tmp_path / "foo.txt").exists()
        assert (tmp_path / "bar.txt").exists()

    def test_skipped_entries_not_counted(self, tmp_path, capsys):
        make_files(tmp_path, "foo.txt", "bar.txt")
        rename_files(str(tmp_path), "^foo", "bar", recursive=False)
        out = capsys.readouterr().out
        assert "0 entry(ies) renamed" in out

    def test_collision_warning_written_to_stderr(self, tmp_path, capsys):
        make_files(tmp_path, "foo.txt", "bar.txt")
        rename_files(str(tmp_path), "^foo", "bar", recursive=False)
        err = capsys.readouterr().err
        assert "SKIP" in err


# ---------------------------------------------------------------------------
# Recursive mode
# ---------------------------------------------------------------------------

class TestRecursiveMode:
    @pytest.fixture()
    def tree(self, tmp_path):
        sub = tmp_path / "sub_dir"
        sub.mkdir()
        (tmp_path / "top_file.txt").touch()
        (sub / "sub_file.txt").touch()
        return tmp_path

    def test_renames_files_in_subdirectories(self, tree):
        rename_files(str(tree), "_", "-", recursive=True)
        assert (tree / "top-file.txt").exists()

    def test_renames_subdirectory_names(self, tree):
        rename_files(str(tree), "^sub_dir$", "renamed_dir", recursive=True)
        assert (tree / "renamed_dir").exists()

    def test_processes_children_before_parents(self, tree):
        # sub_file.txt must be renamed before sub_dir; otherwise the path becomes invalid.
        rename_files(str(tree), "_", "-", recursive=True)
        assert (tree / "sub-dir" / "sub-file.txt").exists()

    def test_does_not_recurse_without_flag(self, tree):
        rename_files(str(tree), "_", "-", recursive=False)
        # sub_dir itself is a direct child and gets renamed …
        assert (tree / "sub-dir").exists()
        # … but the file inside it is not touched.
        assert (tree / "sub-dir" / "sub_file.txt").exists()


# ---------------------------------------------------------------------------
# Backreferences
# ---------------------------------------------------------------------------

class TestBackreferences:
    def test_supports_group_backreferences(self, tmp_path):
        (tmp_path / "2024-01-15.txt").touch()
        rename_files(str(tmp_path), r"(\d{4})-(\d{2})-(\d{2})", r"\3-\2-\1", recursive=False)
        assert (tmp_path / "15-01-2024.txt").exists()
