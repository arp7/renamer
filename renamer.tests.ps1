# Compatible with Pester 3.x

# Import Invoke-RenameByPattern without running the script body.
. (Join-Path $PSScriptRoot 'renamer.ps1')
$script:ScriptPath = Join-Path $PSScriptRoot 'renamer.ps1'
$script:Pwsh = [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName

# Run the script as a subprocess and return ExitCode + Output + Stderr.
function Invoke-Renamer {
    param([string[]]$ScriptArgs)
    $outFile = [IO.Path]::GetTempFileName()
    $errFile = [IO.Path]::GetTempFileName()
    try {
        $argList = @('-NoProfile', '-NonInteractive', '-File', $script:ScriptPath) + $ScriptArgs
        $proc = Start-Process -FilePath $script:Pwsh -ArgumentList $argList `
            -Wait -PassThru -NoNewWindow `
            -RedirectStandardOutput $outFile `
            -RedirectStandardError  $errFile
        return [PSCustomObject]@{
            ExitCode = $proc.ExitCode
            Output   = Get-Content $outFile -Raw
            Stderr   = Get-Content $errFile -Raw
        }
    } finally {
        Remove-Item $outFile, $errFile -ErrorAction SilentlyContinue
    }
}

Describe 'renamer.ps1' {

    Context 'Argument validation' {

        It 'shows help and exits 1 when invoked with no arguments' {
            $r = Invoke-Renamer @()
            $r.ExitCode | Should Be 1
            $r.Output   | Should Match 'SYNOPSIS'
        }

        It 'exits 1 when -Dir is missing' {
            $r = Invoke-Renamer @('-Pattern', 'foo')
            $r.ExitCode | Should Be 1
        }

        It 'exits 1 when -Pattern is missing' {
            $r = Invoke-Renamer @('-Dir', '.')
            $r.ExitCode | Should Be 1
        }

        It 'exits 1 when -Dir does not exist' {
            $r = Invoke-Renamer @('-Dir', 'C:\nonexistent_xyz_abc_123', '-Pattern', 'foo')
            $r.ExitCode | Should Be 1
        }
    }

    Context 'Basic renaming' {

        BeforeEach {
            $script:testDir = Join-Path $TestDrive 'basic'
            Remove-Item $script:testDir -Recurse -Force -ErrorAction SilentlyContinue
            New-Item -ItemType Directory -Path $script:testDir | Out-Null
            'foo_bar.txt', 'baz_qux.txt', 'unchanged.txt' | ForEach-Object {
                New-Item -Path $script:testDir -Name $_ -ItemType File | Out-Null
            }
        }

        It 'renames files whose names match the pattern' {
            Invoke-RenameByPattern -Directory $script:testDir -RegexPattern '_' -Replacement '-'
            Test-Path (Join-Path $script:testDir 'foo-bar.txt') | Should Be $true
            Test-Path (Join-Path $script:testDir 'baz-qux.txt') | Should Be $true
        }

        It 'leaves non-matching files untouched' {
            Invoke-RenameByPattern -Directory $script:testDir -RegexPattern '^NOMATCH' -Replacement 'x'
            (Get-ChildItem $script:testDir).Name -contains 'foo_bar.txt'  | Should Be $true
            (Get-ChildItem $script:testDir).Name -contains 'unchanged.txt' | Should Be $true
        }

        It 'deletes the matched portion when -Replacement is omitted' {
            Invoke-RenameByPattern -Directory $script:testDir -RegexPattern '_bar'
            Test-Path (Join-Path $script:testDir 'foo.txt') | Should Be $true
        }

        It 'returns the count of renamed entries' {
            $count = Invoke-RenameByPattern -Directory $script:testDir -RegexPattern '_' -Replacement '-'
            $count | Should Be 2
        }
    }

    Context 'Dry run' {

        BeforeEach {
            $script:testDir = Join-Path $TestDrive 'dryrun'
            Remove-Item $script:testDir -Recurse -Force -ErrorAction SilentlyContinue
            New-Item -ItemType Directory -Path $script:testDir | Out-Null
            New-Item -Path $script:testDir -Name 'old_name.txt' -ItemType File | Out-Null
        }

        It 'does not rename files when -DryRun is set' {
            Invoke-RenameByPattern -Directory $script:testDir -RegexPattern 'old_name' -Replacement 'new_name' -DryRun
            Test-Path (Join-Path $script:testDir 'old_name.txt') | Should Be $true
            Test-Path (Join-Path $script:testDir 'new_name.txt') | Should Be $false
        }

        It 'still returns the count of entries that would be renamed' {
            $count = Invoke-RenameByPattern -Directory $script:testDir -RegexPattern 'old_name' -Replacement 'new_name' -DryRun
            $count | Should Be 1
        }
    }

    Context 'Collision detection' {

        BeforeEach {
            $script:testDir = Join-Path $TestDrive 'collision'
            Remove-Item $script:testDir -Recurse -Force -ErrorAction SilentlyContinue
            New-Item -ItemType Directory -Path $script:testDir | Out-Null
            New-Item -Path $script:testDir -Name 'foo.txt' -ItemType File | Out-Null
            New-Item -Path $script:testDir -Name 'bar.txt' -ItemType File | Out-Null
        }

        It 'skips the rename when the destination already exists' {
            Invoke-RenameByPattern -Directory $script:testDir -RegexPattern '^foo' -Replacement 'bar' -WarningAction SilentlyContinue
            Test-Path (Join-Path $script:testDir 'foo.txt') | Should Be $true
            Test-Path (Join-Path $script:testDir 'bar.txt') | Should Be $true
        }

        It 'does not count skipped entries' {
            $count = Invoke-RenameByPattern -Directory $script:testDir -RegexPattern '^foo' -Replacement 'bar' -WarningAction SilentlyContinue
            $count | Should Be 0
        }
    }

    Context 'Recursive mode' {

        BeforeEach {
            $script:testDir = Join-Path $TestDrive 'recursive'
            $script:subDir  = Join-Path $script:testDir 'sub_dir'
            Remove-Item $script:testDir -Recurse -Force -ErrorAction SilentlyContinue
            New-Item -ItemType Directory -Path $script:subDir -Force | Out-Null
            New-Item -Path $script:testDir -Name 'top_file.txt' -ItemType File | Out-Null
            New-Item -Path $script:subDir  -Name 'sub_file.txt' -ItemType File | Out-Null
        }

        It 'renames files in subdirectories' {
            Invoke-RenameByPattern -Directory $script:testDir -RegexPattern '_' -Replacement '-' -Recurse
            Test-Path (Join-Path $script:testDir 'top-file.txt') | Should Be $true
        }

        It 'renames subdirectory names themselves' {
            Invoke-RenameByPattern -Directory $script:testDir -RegexPattern '^sub_dir$' -Replacement 'renamed_dir' -Recurse
            Test-Path (Join-Path $script:testDir 'renamed_dir') | Should Be $true
        }

        It 'processes children before parents so renames stay consistent' {
            # sub_file.txt must be renamed before sub_dir, or its path becomes invalid.
            Invoke-RenameByPattern -Directory $script:testDir -RegexPattern '_' -Replacement '-' -Recurse
            Test-Path (Join-Path (Join-Path $script:testDir 'sub-dir') 'sub-file.txt') | Should Be $true
        }

        It 'does not recurse when -Recurse is omitted' {
            Invoke-RenameByPattern -Directory $script:testDir -RegexPattern '_' -Replacement '-'
            # sub_dir itself is a direct child so it gets renamed...
            Test-Path (Join-Path $script:testDir 'sub-dir') | Should Be $true
            # ...but sub_file.txt inside it is not touched.
            Test-Path (Join-Path (Join-Path $script:testDir 'sub-dir') 'sub_file.txt') | Should Be $true
        }
    }

    Context 'Backreferences' {

        BeforeEach {
            $script:testDir = Join-Path $TestDrive 'backref'
            Remove-Item $script:testDir -Recurse -Force -ErrorAction SilentlyContinue
            New-Item -ItemType Directory -Path $script:testDir | Out-Null
            New-Item -Path $script:testDir -Name '2024-01-15.txt' -ItemType File | Out-Null
        }

        It 'supports $1 $2 backreferences in the replacement string' {
            Invoke-RenameByPattern -Directory $script:testDir `
                -RegexPattern '(\d{4})-(\d{2})-(\d{2})' `
                -Replacement '$3-$2-$1'
            Test-Path (Join-Path $script:testDir '15-01-2024.txt') | Should Be $true
        }
    }
}
