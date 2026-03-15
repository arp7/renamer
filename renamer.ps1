<#
.SYNOPSIS
    Rename files and directories using a regex find-and-replace on their names.

.DESCRIPTION
    Applies a .NET regex substitution to the names of every file and directory
    inside the specified folder.

    NOTE: PowerShell's -replace operator uses $1, $2, ... for backreferences,
    not \1, \2 as in Python/Perl.

.PARAMETER Dir
    Path to the directory whose contents will be renamed.

.PARAMETER Pattern
    .NET-compatible regex pattern to match against each entry's name.

.PARAMETER To
    Replacement string. Supports $1, $2, ... backreferences.
    Defaults to an empty string, effectively deleting the matched portion.

.PARAMETER Recursive
    Recurse into subdirectories. Entries are processed bottom-up so that
    renaming a parent directory does not invalidate paths to its children.

.PARAMETER DryRun
    Show what would be renamed without making any changes.

.EXAMPLE
    .\renamer.ps1 -Dir C:\photos -Pattern '^IMG_' -To 'photo_'

    Renames IMG_001.jpg -> photo_001.jpg, etc.

.EXAMPLE
    .\renamer.ps1 -Dir . -Pattern '(\d{4})-(\d{2})-(\d{2})' -To '$3-$2-$1' -DryRun

    Preview reversing date segments: 2024-01-15.log -> 15-01-2024.log

.EXAMPLE
    .\renamer.ps1 -Dir . -Pattern '\.bak$' -Recursive

    Strip the .bak extension from every file in the tree.
#>
[CmdletBinding()]
param(
    [string]$Dir,
    [string]$Pattern,
    [string]$To = '',
    [switch]$Recursive,
    [switch]$DryRun
)

function Invoke-RenameByPattern {
    param(
        [string]$Directory,
        [string]$RegexPattern,
        [string]$Replacement = '',
        [switch]$Recurse,
        [switch]$DryRun
    )

    if ($Recurse) {
        # Sort descending by path depth so children are processed before parents.
        $items = Get-ChildItem -LiteralPath $Directory -Recurse |
            Sort-Object { ($_.FullName -split '[/\\]').Count } -Descending
    } else {
        $items = Get-ChildItem -LiteralPath $Directory
    }

    $renamed = 0

    foreach ($item in $items) {
        $oldName = $item.Name
        $newName = $oldName -replace $RegexPattern, $Replacement

        if ($newName -eq $oldName) { continue }

        $parentPath = Split-Path $item.FullName -Parent
        $newPath    = Join-Path $parentPath $newName

        if (Test-Path -LiteralPath $newPath) {
            Write-Warning "SKIP: '$newPath' already exists"
            continue
        }

        Write-Host "'$($item.FullName)' -> '$newPath'"
        if (-not $DryRun) {
            Rename-Item -LiteralPath $item.FullName -NewName $newName
        }
        $renamed++
    }

    $action = if ($DryRun) { 'would be renamed' } else { 'renamed' }
    Write-Host ""
    Write-Host "$renamed entry(ies) $action."
    return $renamed
}

# Run only when invoked directly, not when dot-sourced for testing.
if ($MyInvocation.InvocationName -ne '.') {
    if ($PSBoundParameters.Count -eq 0) {
        Get-Help $MyInvocation.MyCommand.Path -Detailed
        exit 1
    }

    if (-not $Dir) {
        Write-Error '-Dir is required.'
        exit 1
    }

    if (-not $Pattern) {
        Write-Error '-Pattern is required.'
        exit 1
    }

    if (-not (Test-Path -LiteralPath $Dir -PathType Container)) {
        Write-Error "'$Dir' is not a directory."
        exit 1
    }

    Invoke-RenameByPattern -Directory $Dir -RegexPattern $Pattern -Replacement $To `
        -Recurse:$Recursive -DryRun:$DryRun
}
