# renamer

Rename files and directories by applying a regex find-and-replace to their names.

## Usage

**Python**
```
python renamer.py --dir <dir> --pattern <regex> [--to <replacement>] [-r] [-n]
```

**PowerShell**
```
.\renamer.ps1 -Dir <dir> -Pattern <regex> [-To <replacement>] [-Recursive] [-DryRun]
```

| Flag | Description |
|---|---|
| `--dir` / `-Dir` | Directory to operate on |
| `--pattern` / `-Pattern` | Regex pattern to match in file/directory names |
| `--to` / `-To` | Replacement string (default: `""`, deletes the match) |
| `-r` / `-Recursive` | Recurse into subdirectories (bottom-up) |
| `-n` / `-DryRun` | Preview changes without renaming anything |

> **Backreferences:** Python uses `\1`, `\2`, … — PowerShell uses `$1`, `$2`, …

## Examples

Strip a prefix:
```
python renamer.py --dir ~/photos --pattern "^IMG_" --to "photo_"
.\renamer.ps1  -Dir  ~/photos  -Pattern "^IMG_"  -To "photo_"
```

Reverse date segments (`2024-01-15` → `15-01-2024`):
```
python renamer.py --dir . --pattern "(\d{4})-(\d{2})-(\d{2})" --to "\3-\2-\1" -n
.\renamer.ps1  -Dir  .  -Pattern "(\d{4})-(\d{2})-(\d{2})"  -To '$3-$2-$1'  -DryRun
```

Remove `.bak` extension everywhere in a tree:
```
python renamer.py --dir . --pattern "\.bak$" -r
.\renamer.ps1  -Dir  .  -Pattern "\.bak$"  -Recursive
```

## Tests

```
# Python (requires pytest)
python -m pytest test_renamer.py

# PowerShell (requires Pester 3+)
Invoke-Pester .\renamer.tests.ps1
```
