"""Tests for renamer.py"""

import subprocess
import sys
from pathlib import Path

import pytest

from renamer import normalize_name, rename_files, unique_path, _atomic_rename


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
        rename_files(str(tmp_path), [("_", "-")], recursive=False)
        assert (tmp_path / "foo-bar.txt").exists()
        assert (tmp_path / "baz-qux.txt").exists()

    def test_leaves_non_matching_files_untouched(self, tmp_path):
        make_files(tmp_path, "foo_bar.txt", "unchanged.txt")
        rename_files(str(tmp_path), [("^NOMATCH", "x")], recursive=False)
        assert (tmp_path / "foo_bar.txt").exists()
        assert (tmp_path / "unchanged.txt").exists()

    def test_deletes_matched_portion_when_replacement_is_empty(self, tmp_path):
        make_files(tmp_path, "foo_bar.txt")
        rename_files(str(tmp_path), [("_bar", "")], recursive=False)
        assert (tmp_path / "foo.txt").exists()
        assert not (tmp_path / "foo_bar.txt").exists()

    def test_returns_count_of_renamed_entries(self, tmp_path, capsys):
        make_files(tmp_path, "foo_bar.txt", "baz_qux.txt", "unchanged.txt")
        rename_files(str(tmp_path), [("_", "-")], recursive=False)
        out = capsys.readouterr().out
        assert "2 entry(ies) renamed" in out


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_does_not_rename_files(self, tmp_path):
        make_files(tmp_path, "old_name.txt")
        rename_files(str(tmp_path), [("old_name", "new_name")], recursive=False, dry_run=True)
        assert (tmp_path / "old_name.txt").exists()
        assert not (tmp_path / "new_name.txt").exists()

    def test_reports_would_be_renamed_count(self, tmp_path, capsys):
        make_files(tmp_path, "old_name.txt")
        rename_files(str(tmp_path), [("old_name", "new_name")], recursive=False, dry_run=True)
        out = capsys.readouterr().out
        assert "1 entry(ies) would be renamed" in out

    def test_does_not_rename_on_within_run_collision(self, tmp_path):
        # Verify dry-run really doesn't touch the filesystem even with collisions.
        make_files(tmp_path, "a.txt", "b.txt")
        rename_files(str(tmp_path), [("^[ab]", "out")], recursive=False, dry_run=True)
        assert (tmp_path / "a.txt").exists()
        assert (tmp_path / "b.txt").exists()
        assert not (tmp_path / "out.txt").exists()


# ---------------------------------------------------------------------------
# Collision avoidance
# ---------------------------------------------------------------------------

class TestUniquePath:
    def test_free_path_returned_unchanged(self, tmp_path):
        p = str(tmp_path / "new.txt")
        assert unique_path(p) == p

    def test_appends_0001_when_taken(self, tmp_path):
        (tmp_path / "file.txt").touch()
        result = unique_path(str(tmp_path / "file.txt"))
        assert result == str(tmp_path / "file_0001.txt")

    def test_increments_past_0001_when_also_taken(self, tmp_path):
        (tmp_path / "file.txt").touch()
        (tmp_path / "file_0001.txt").touch()
        result = unique_path(str(tmp_path / "file.txt"))
        assert result == str(tmp_path / "file_0002.txt")

    def test_preserves_extension(self, tmp_path):
        (tmp_path / "archive.tar.gz").touch()
        result = unique_path(str(tmp_path / "archive.tar.gz"))
        assert result == str(tmp_path / "archive.tar_0001.gz")

    def test_no_extension(self, tmp_path):
        (tmp_path / "noext").touch()
        result = unique_path(str(tmp_path / "noext"))
        assert result == str(tmp_path / "noext_0001")

    def test_claimed_path_avoided_even_when_not_on_disk(self, tmp_path):
        p = str(tmp_path / "file.txt")
        claimed = {p}
        result = unique_path(p, claimed)
        assert result == str(tmp_path / "file_0001.txt")

    def test_claimed_and_disk_both_checked(self, tmp_path):
        (tmp_path / "file.txt").touch()
        claimed = {str(tmp_path / "file_0001.txt")}
        result = unique_path(str(tmp_path / "file.txt"), claimed)
        assert result == str(tmp_path / "file_0002.txt")


class TestCollisionAvoidance:
    def test_appends_suffix_instead_of_skipping(self, tmp_path):
        make_files(tmp_path, "foo.txt", "bar.txt")
        rename_files(str(tmp_path), [("^foo", "bar")], recursive=False)
        assert not (tmp_path / "foo.txt").exists()
        assert (tmp_path / "bar.txt").exists()
        assert (tmp_path / "bar_0001.txt").exists()

    def test_increments_suffix_for_each_collision(self, tmp_path):
        make_files(tmp_path, "foo.txt", "bar.txt", "bar_0001.txt")
        rename_files(str(tmp_path), [("^foo", "bar")], recursive=False)
        assert (tmp_path / "bar_0002.txt").exists()

    def test_collision_rename_is_counted(self, tmp_path, capsys):
        make_files(tmp_path, "foo.txt", "bar.txt")
        rename_files(str(tmp_path), [("^foo", "bar")], recursive=False)
        out = capsys.readouterr().out
        assert "1 entry(ies) renamed" in out

    def test_two_files_renamed_to_same_target_get_distinct_names(self, tmp_path):
        # Neither "out.txt" exists beforehand — collision is purely within-run.
        make_files(tmp_path, "a.txt", "b.txt")
        rename_files(str(tmp_path), [("^[ab]", "out")], recursive=False)
        results = set(p.name for p in tmp_path.iterdir())
        assert "out.txt" in results
        assert "out_0001.txt" in results

    def test_dry_run_within_run_collision_shows_distinct_targets(self, tmp_path, capsys):
        # In dry-run mode no files are renamed, so the claimed-set is essential
        # to produce distinct target paths for files that both resolve to the same name.
        make_files(tmp_path, "a.txt", "b.txt")
        rename_files(str(tmp_path), [("^[ab]", "out")], recursive=False, dry_run=True)
        out = capsys.readouterr().out
        assert "out.txt" in out
        assert "out_0001.txt" in out


class TestAtomicRename:
    def test_renames_file(self, tmp_path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.touch()
        _atomic_rename(str(src), str(dst))
        assert dst.exists()
        assert not src.exists()

    def test_placeholder_removed_on_rename_failure(self, tmp_path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        # src does not exist — rename must fail
        with pytest.raises(Exception):
            _atomic_rename(str(src), str(dst))
        # placeholder must be cleaned up
        assert not dst.exists()


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
        rename_files(str(tree), [("_", "-")], recursive=True)
        assert (tree / "top-file.txt").exists()

    def test_renames_subdirectory_names(self, tree):
        rename_files(str(tree), [("^sub_dir$", "renamed_dir")], recursive=True)
        assert (tree / "renamed_dir").exists()

    def test_processes_children_before_parents(self, tree):
        # sub_file.txt must be renamed before sub_dir; otherwise the path becomes invalid.
        rename_files(str(tree), [("_", "-")], recursive=True)
        assert (tree / "sub-dir" / "sub-file.txt").exists()

    def test_does_not_recurse_without_flag(self, tree):
        rename_files(str(tree), [("_", "-")], recursive=False)
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
        rename_files(str(tmp_path), [(r"(\d{4})-(\d{2})-(\d{2})", r"\3-\2-\1")], recursive=False)
        assert (tmp_path / "15-01-2024.txt").exists()


# ---------------------------------------------------------------------------
# Multiple patterns
# ---------------------------------------------------------------------------

class TestMultiplePatterns:
    def test_two_patterns_applied_in_sequence(self, tmp_path):
        make_files(tmp_path, "foo_bar.txt")
        # Step 1: _ → -  →  foo-bar.txt
        # Step 2: bar → baz  →  foo-baz.txt
        rename_files(str(tmp_path), [("_", "-"), ("bar", "baz")], recursive=False)
        assert (tmp_path / "foo-baz.txt").exists()

    def test_output_of_first_pattern_feeds_second(self, tmp_path):
        make_files(tmp_path, "aXbYc.txt")
        # Step 1: X → Y  →  aYbYc.txt
        # Step 2: Y → Z  →  aZbZc.txt  (both Y's replaced, including the one just introduced)
        rename_files(str(tmp_path), [("X", "Y"), ("Y", "Z")], recursive=False)
        assert (tmp_path / "aZbZc.txt").exists()

    def test_three_patterns(self, tmp_path):
        make_files(tmp_path, "a_b_c.txt")
        rename_files(str(tmp_path), [("a", "x"), ("b", "y"), ("c", "z")], recursive=False)
        assert (tmp_path / "x_y_z.txt").exists()

    def test_cli_two_patterns_with_replacements(self, tmp_path):
        make_files(tmp_path, "foo_bar.txt")
        code, _, _ = run_cli(
            "--dir", str(tmp_path),
            "--pattern", "_", "--to", "-",
            "--pattern", "bar", "--to", "baz",
        )
        assert code == 0
        assert (tmp_path / "foo-baz.txt").exists()

    def test_cli_pattern_without_to_deletes_match(self, tmp_path):
        make_files(tmp_path, "prefix_name.txt")
        code, _, _ = run_cli("--dir", str(tmp_path), "--pattern", "prefix_")
        assert code == 0
        assert (tmp_path / "name.txt").exists()

    def test_cli_mixed_patterns_some_with_to_some_without(self, tmp_path):
        make_files(tmp_path, "foo_bar_baz.txt")
        # First pattern has --to, second does not (deletes match)
        code, _, _ = run_cli(
            "--dir", str(tmp_path),
            "--pattern", "foo", "--to", "qux",
            "--pattern", "_bar",
        )
        assert code == 0
        assert (tmp_path / "qux_baz.txt").exists()


# ---------------------------------------------------------------------------
# normalize_name unit tests
# ---------------------------------------------------------------------------

class TestNormalizeName:
    # --- Non-printable ASCII characters → '-' ---

    @pytest.mark.parametrize("char", [
        "\x00",  # NUL
        "\x01",  # SOH
        "\x02",  # STX
        "\x03",  # ETX
        "\x04",  # EOT
        "\x05",  # ENQ
        "\x06",  # ACK
        "\x07",  # BEL
        "\x08",  # BS
        "\x0e",  # SO
        "\x0f",  # SI
        "\x10",  # DLE
        "\x11",  # DC1
        "\x12",  # DC2
        "\x13",  # DC3
        "\x14",  # DC4
        "\x15",  # NAK
        "\x16",  # SYN
        "\x17",  # ETB
        "\x18",  # CAN
        "\x19",  # EM
        "\x1a",  # SUB
        "\x1b",  # ESC
        "\x1c",  # FS
        "\x1d",  # GS
        "\x1e",  # RS
        "\x1f",  # US
        "\x7f",  # DEL
    ])
    def test_non_printable_char_replaced_with_dash(self, char):
        assert normalize_name(f"a{char}b") == "a-b"

    def test_multiple_non_printable_chars_each_replaced(self):
        assert normalize_name("\x00\x01\x7f") == "---"

    def test_non_printable_at_start_and_end(self):
        assert normalize_name("\x01hello\x1f") == "-hello-"

    # --- Space-like control characters → standard space (0x20) ---

    @pytest.mark.parametrize("char,name", [
        ("\x09", "HT / tab"),
        ("\x0a", "LF / newline"),
        ("\x0b", "VT / vertical tab"),
        ("\x0c", "FF / form feed"),
        ("\x0d", "CR / carriage return"),
    ])
    def test_space_like_char_replaced_with_space(self, char, name):
        assert normalize_name(f"a{char}b") == "a b", f"failed for {name}"

    def test_crlf_pair_collapses_to_single_space(self):
        # \r\n → two spaces → collapsed to one
        assert normalize_name("a\r\nb") == "a b"

    def test_mixed_space_like_chars_collapse_to_single_space(self):
        assert normalize_name("a\t\n\r\v\fb") == "a b"

    # --- Multiple spaces → single space ---

    def test_two_spaces_collapsed(self):
        assert normalize_name("a  b") == "a b"

    def test_many_spaces_collapsed(self):
        assert normalize_name("a     b") == "a b"

    def test_leading_spaces_stripped(self):
        assert normalize_name("  hello") == "hello"

    def test_trailing_spaces_stripped(self):
        assert normalize_name("hello  ") == "hello"

    def test_leading_and_trailing_spaces_stripped(self):
        assert normalize_name("  hello  ") == "hello"

    def test_spaces_only_becomes_empty(self):
        assert normalize_name("   ") == ""

    def test_leading_tab_stripped(self):
        # Tab → space → stripped
        assert normalize_name("\thello") == "hello"

    def test_internal_spaces_not_stripped(self):
        assert normalize_name("hello world") == "hello world"

    # --- Strings that should pass through unchanged ---

    def test_already_clean_name_unchanged(self):
        assert normalize_name("report.pdf") == "report.pdf"

    def test_printable_ascii_with_spaces_unchanged(self):
        name = "hello world (2024).txt"
        assert normalize_name(name) == name

    def test_empty_string_unchanged(self):
        assert normalize_name("") == ""

    # --- Ordering: space-like chars become spaces before non-printable sweep ---

    def test_space_like_not_replaced_by_dash(self):
        # Tabs must become spaces, not dashes
        assert normalize_name("a\tb") == "a b"
        assert "-" not in normalize_name("a\tb")

    # --- Real-world examples ---

    def test_filename_with_escape_sequence(self):
        assert normalize_name("file\x1bname.txt") == "file-name.txt"

    def test_filename_with_nul_byte(self):
        assert normalize_name("data\x00record.csv") == "data-record.csv"

    def test_filename_messy_whitespace(self):
        assert normalize_name("My  Document\t(final).docx") == "My Document (final).docx"


# ---------------------------------------------------------------------------
# --normalize integration tests (filesystem)
# ---------------------------------------------------------------------------

class TestNormalizeOption:
    def test_collapses_multiple_spaces_in_filename(self, tmp_path):
        (tmp_path / "too  many   spaces.txt").touch()
        rename_files(str(tmp_path), [], recursive=False, normalize=True)
        assert (tmp_path / "too many spaces.txt").exists()

    def test_already_clean_file_not_renamed(self, tmp_path, capsys):
        (tmp_path / "clean.txt").touch()
        rename_files(str(tmp_path), [], recursive=False, normalize=True)
        out = capsys.readouterr().out
        assert "0 entry(ies) renamed" in out

    def test_normalize_without_pattern_is_valid(self, tmp_path):
        (tmp_path / "double  space.txt").touch()
        rename_files(str(tmp_path), [], recursive=False, normalize=True)
        assert (tmp_path / "double space.txt").exists()

    def test_cli_normalize_flag(self, tmp_path):
        (tmp_path / "too  many  spaces.txt").touch()
        code, _, _ = run_cli("--dir", str(tmp_path), "--normalize")
        assert code == 0
        assert (tmp_path / "too many spaces.txt").exists()

    def test_cli_requires_pattern_or_normalize(self):
        code, _, stderr = run_cli("--dir", ".")
        assert code != 0
        assert "pattern" in stderr.lower() or "normalize" in stderr.lower() or "required" in stderr.lower()

    def test_cli_normalize_and_pattern_are_mutually_exclusive(self):
        code, _, stderr = run_cli("--dir", ".", "--normalize", "--pattern", "foo")
        assert code != 0
        assert "mutually exclusive" in stderr.lower()
