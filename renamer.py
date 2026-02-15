#!/usr/bin/env python3
"""Rename files and directories by applying a regex substitution to their names."""

import argparse
import os
import re
import sys


def rename_files(directory, pattern_from, pattern_to, recursive, dry_run=False):
    regex = re.compile(pattern_from)
    renamed = 0

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
        new_name = regex.sub(pattern_to, old_name)
        if new_name == old_name:
            continue

        old_path = os.path.join(parent, old_name)
        new_path = os.path.join(parent, new_name)

        if os.path.exists(new_path):
            print(f"SKIP: '{new_path}' already exists", file=sys.stderr)
            continue

        print(f"'{old_path}' -> '{new_path}'")
        if not dry_run:
            os.rename(old_path, new_path)
        renamed += 1

    action = "would be renamed" if dry_run else "renamed"
    print(f"\n{renamed} entry(ies) {action}.")


def main():
    parser = argparse.ArgumentParser(
        description="Rename files by applying a regex substitution to their names."
    )
    parser.add_argument("--dir", required=True, help="Directory containing files to rename")
    parser.add_argument("--pattern", required=True, help="Regex pattern to match in file names")
    parser.add_argument(
        "--to", default="", nargs="?", const="",
        help=r"Replacement pattern (use \1, \2 for backreferences); omit to delete matches",
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
    args = parser.parse_args()

    if not os.path.isdir(args.dir):
        print(f"Error: '{args.dir}' is not a directory", file=sys.stderr)
        sys.exit(1)

    rename_files(args.dir, args.pattern, args.to, args.recursive, args.dry_run)


if __name__ == "__main__":
    main()
