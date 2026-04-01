#!/usr/bin/env python3
"""
Collapse single-child directory chains.

For every directory that contains exactly one child (which must be a directory
and nothing else), the child is moved one level up and the now-empty parent
is deleted.
"""

import argparse
import os
import shutil
import sys


def collapse_dirs(path: str, dry_run: bool = False) -> tuple[int, int]:
    """
    Recursively collapse single-child directory chains under *path*.

    A directory qualifies for collapsing when it contains exactly one entry
    and that entry is a directory (not a file, symlink, etc.).

    Returns (collapsed, errors).
    """
    collapsed = 0
    errors = 0

    try:
        entries = list(os.scandir(path))
    except PermissionError:
        print(f"ERROR: permission denied: '{path}'", file=sys.stderr)
        return 0, 1
    except FileNotFoundError:
        return 0, 0

    # Bottom-up: recurse first so nested chains are already resolved before
    # we inspect this level.
    for entry in entries:
        if entry.is_dir(follow_symlinks=False):
            c, e = collapse_dirs(entry.path, dry_run)
            collapsed += c
            errors += e

    # Re-scan: recursive calls may have restructured the subtree.
    try:
        entries = list(os.scandir(path))
    except (PermissionError, FileNotFoundError):
        return collapsed, errors

    for entry in entries:
        if not entry.is_dir(follow_symlinks=False):
            continue

        try:
            children = list(os.scandir(entry.path))
        except PermissionError:
            print(f"ERROR: permission denied: '{entry.path}'", file=sys.stderr)
            errors += 1
            continue

        # Collapse only when the sole content is a single sub-directory.
        if len(children) != 1 or not children[0].is_dir(follow_symlinks=False):
            continue

        child = children[0]
        dest = os.path.join(path, child.name)

        # Guard against overwriting an existing entry (use lexists to also
        # catch broken symlinks).
        if os.path.lexists(dest):
            print(
                f"ERROR: cannot collapse '{entry.path}' — "
                f"'{dest}' already exists, skipping",
                file=sys.stderr,
            )
            errors += 1
            continue

        tag = "[DRY RUN] " if dry_run else ""
        print(f"{tag}move  '{child.path}'  ->  '{dest}'")
        print(f"{tag}rmdir '{entry.path}'")

        if not dry_run:
            try:
                shutil.move(child.path, dest)
                os.rmdir(entry.path)
            except OSError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                errors += 1
                continue

        collapsed += 1

    return collapsed, errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Collapse single-child directory chains: when a directory contains "
            "only one child directory (and nothing else), move that child one "
            "level up and remove the now-empty parent."
        )
    )
    parser.add_argument("directory", help="Root directory to process")
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would be done without making any changes",
    )
    args = parser.parse_args()

    root = os.path.abspath(args.directory)
    if not os.path.isdir(root):
        print(f"ERROR: '{args.directory}' is not a directory", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("Dry-run mode — no changes will be made.\n")

    collapsed, errors = collapse_dirs(root, args.dry_run)

    verb = "would be collapsed" if args.dry_run else "collapsed"
    dirs = "directory" if collapsed == 1 else "directories"
    print(f"\n{collapsed} {dirs} {verb}, {errors} error(s).")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
