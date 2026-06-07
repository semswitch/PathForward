# PathForward task runner (Windows / PowerShell).  Usage:  ./tasks.ps1 <task>
param([Parameter(Position = 0)][string]$Task = "help")

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

switch ($Task) {
    "test" { python -m unittest discover -s "$root\tests" -t "$root" -v }
    "data" { python "$root\scripts\generate_data.py" }
    "mirror" { python "$root\scripts\build_mirror.py" }
    "demo" { python "$root\scripts\run_demo.py" }
    "fixture" { python "$root\scripts\export_web_fixture.py" }
    "all" {
        python "$root\scripts\generate_data.py"
        python "$root\scripts\build_mirror.py"
        python "$root\scripts\export_web_fixture.py"
        python -m unittest discover -s "$root\tests" -t "$root"
        python "$root\scripts\run_demo.py"
    }
    "azure" { pip install -r "$root\requirements.txt" }
    default {
        Write-Output "PathForward tasks:"
        Write-Output "  ./tasks.ps1 test     run the unit suite"
        Write-Output "  ./tasks.ps1 data     generate synthetic ontology + learner responses"
        Write-Output "  ./tasks.ps1 mirror   build + validate the Search-mirror docs"
        Write-Output "  ./tasks.ps1 fixture  export web/ demo fixture JSON"
        Write-Output "  ./tasks.ps1 demo     run the offline end-to-end demo"
        Write-Output "  ./tasks.ps1 all      data + mirror + fixture + tests + demo"
        Write-Output "  ./tasks.ps1 azure    pip install the Azure layer (Day 0+)"
    }
}
