#!/usr/bin/env python3
"""Rename files and directories by applying regex substitutions to their names."""

import argparse
import os
import re
import sys


def normalize_name(name):
    """Normalize a filename by cleaning up whitespace and non-printable characters."""
    # Replace space-like control characters (tab, LF, CR, VT, FF) with standard space
    name = re.sub(r'[\t\n\r\v\f]', ' ', name)
    # Replace remaining non-printable ASCII characters (0x00-0x1F and DEL 0x7F) with '-'
    name = re.sub(r'[\x00-\x1f\x7f]', '-', name)
    # Collapse runs of multiple spaces into a single space
    name = re.sub(r' {2,}', ' ', name)
    # Remove any leading or trailing spaces
    name = name.strip()
    return name


def unique_path(path, claimed=()):
    """Return path if free (not on disk, not in claimed); otherwise append _0001, _0002 …"""
    if path not in claimed and not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    n = 1
    while True:
        candidate = f"{root}_{n:04d}{ext}"
        if candidate not in claimed and not os.path.exists(candidate):
            return candidate
        n += 1


def _atomic_rename(old_path, new_path):
    """Rename old_path to new_path, atomically claiming new_path first to close the TOCTOU window."""
    # Create an empty placeholder at new_path with O_EXCL so no other process can
    # sneak in between our path-selection and the actual rename.
    fd = os.open(new_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    try:
        # os.replace atomically overwrites the placeholder with the renamed file.
        os.replace(old_path, new_path)
    except Exception:
        try:
            os.unlink(new_path)
        except OSError:
            pass
        raise


def rename_files(directory, patterns, recursive, dry_run=False, normalize=False):
    compiled = [(re.compile(p), r) for p, r in patterns]
    renamed = 0
    claimed = set()  # target paths reserved in this run (for dry-run correctness too)

    if recursive:
        # Walk bottom-up so renaming a directory doesn't invalidate
        # paths of entries deeper in the tree that are yet to be processed.
        entries = []
        for root, dirs, files in os.walk(directory, topdown=False):
            for name in files:
                entries.append((root, name))
            for name in dirs:
                entries.append((root, name))
    else:
        entries = [(directory, name) for name in os.listdir(directory)]

    for parent, old_name in entries:
        new_name = normalize_name(old_name) if normalize else old_name
        for regex, replacement in compiled:
            new_name = regex.sub(replacement, new_name)
        if new_name == old_name:
            continue

        old_path = os.path.join(parent, old_name)
        new_path = unique_path(os.path.join(parent, new_name), claimed)
        claimed.add(new_path)

        print(f"'{old_path}' -> '{new_path}'")
        if not dry_run:
            _atomic_rename(old_path, new_path)
        renamed += 1

    action = "would be renamed" if dry_run else "renamed"
    print(f"\n{renamed} entry(ies) {action}.")


class _PatternAction(argparse.Action):
    """Append a new [pattern, ''] pair to namespace.patterns."""
    def __call__(self, parser, namespace, values, option_string=None):
        pairs = getattr(namespace, 'patterns', None) or []
        pairs.append([values, ""])
        setattr(namespace, 'patterns', pairs)


class _ToAction(argparse.Action):
    """Set the replacement string for the most recently added pattern."""
    def __call__(self, parser, namespace, values, option_string=None):
        pairs = getattr(namespace, 'patterns', None)
        if not pairs:
            parser.error("--to requires a preceding --pattern")
        pairs[-1][1] = "" if values is None else values


def main():
    parser = argparse.ArgumentParser(
        description="Rename files by applying regex substitutions to their names."
    )
    parser.add_argument("--dir", required=True, help="Directory containing files to rename")
    parser.add_argument(
        "--pattern",
        dest="patterns",
        action=_PatternAction,
        metavar="PATTERN",
        help="Regex pattern to match in file names (may be repeated)",
    )
    parser.add_argument(
        "--to",
        action=_ToAction,
        dest="to",
        nargs="?",
        const="",
        default=None,
        metavar="REPLACEMENT",
        help=r"Replacement for the preceding --pattern (default: '' deletes the match; supports \1 backrefs)",
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recurse into subdirectories",
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Only print what would be renamed without actually renaming",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help=(
            "Normalize filenames: replace non-printable ASCII characters with '-', "
            "replace space-like characters with a standard space, "
            "and collapse multiple spaces into one. "
            "Mutually exclusive with --pattern."
        ),
    )
    args = parser.parse_args()
    patterns = args.patterns or []

    if args.normalize and patterns:
        parser.error("--normalize and --pattern are mutually exclusive")
    if not patterns and not args.normalize:
        parser.error("at least one of --pattern or --normalize is required")
    if not os.path.isdir(args.dir):
        print(f"Error: '{args.dir}' is not a directory", file=sys.stderr)
        sys.exit(1)

    rename_files(args.dir, patterns, args.recursive, args.dry_run, args.normalize)


if __name__ == "__main__":
    main()
