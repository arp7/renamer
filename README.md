# renamer

Rename files and directories by applying regex find-and-replace rules to their names.

## Usage

**Python**
```
python renamer.py --dir <dir> (--pattern <regex> [--to <replacement>] … | --normalize) [-r] [-n]
```

**PowerShell**
```
.\renamer.ps1 -Dir <dir> -Pattern <regex> [-To <replacement>] [-Recursive] [-DryRun]
```

| Flag | Description |
|---|---|
| `--dir` / `-Dir` | Directory to operate on |
| `--pattern` / `-Pattern` | Regex pattern to match in file/directory names (Python: repeatable) |
| `--to` / `-To` | Replacement for the preceding `--pattern` (default: `""`, deletes the match) |
| `--normalize` | Normalize filenames: non-printable ASCII → `-`, space-like chars → space, runs of spaces → one space. Mutually exclusive with `--pattern`. |
| `-r` / `-Recursive` | Recurse into subdirectories (bottom-up, so children are renamed before parents) |
| `-n` / `-DryRun` | Preview changes without renaming anything |

> **Backreferences:** Python uses `\1`, `\2`, … — PowerShell uses `$1`, `$2`, …

> **Collision avoidance:** if a rename would overwrite an existing file, a `_0001`, `_0002`, … suffix is appended automatically to find a free name.

## Multiple patterns (Python only)

`--pattern` / `--to` pairs can be repeated and are applied left-to-right in sequence, each operating on the result of the previous step:

```
python renamer.py --dir . --pattern "^IMG_" --to "photo_" --pattern "\.jpeg$" --to ".jpg"
```

If `--to` is omitted for a `--pattern`, the match is deleted (equivalent to `--to ""`):

```
python renamer.py --dir . --pattern "\(copy\)" --pattern "  " --to " "
```

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

Normalize filenames downloaded from the web (clean up spaces and control characters):
```
python renamer.py --dir ~/downloads --normalize -r
```

Chain two substitutions — first convert underscores to spaces, then title-case separators:
```
python renamer.py --dir . --pattern "_" --to " " --pattern "^\w" --to ...
```

## Tests

```
# Python (requires pytest)
python -m pytest test_renamer.py

# PowerShell (requires Pester 3+)
Invoke-Pester .\renamer.tests.ps1
```
