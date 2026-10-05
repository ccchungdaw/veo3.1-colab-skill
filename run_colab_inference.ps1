# PowerShell launcher for Google Veo 3.1 Colab inference
param (
    [Parameter(Mandatory=$true)]
    [string]$Prompt,
    [string[]]$Image = @(),
    [string]$FirstFrame,
    [string]$LastFrame,
    [string]$Output,
    [string]$Model = "veo-3.1-generate-preview",
    [int]$Duration = 5,
    [string]$AspectRatio = "16:9",
    [string]$Resolution = "1080p",
    [string]$Gpu = "none",
    [int]$Timeout = 1200,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host @"
Usage:
  .\run_colab_inference.ps1 -Prompt <text|file> [-Image <path> ...] [-FirstFrame <path>] [-Output <path>] [options]

Options:
  -Prompt <str>       Prompt text or path to prompt text file (required)
  -Image <paths>      Reference images (up to 3)
  -FirstFrame <path>  First frame image
  -LastFrame <path>   Last frame image
  -Output <path>      Output MP4 target path
  -Model <name>       Veo model (default: veo-3.1-generate-preview)
  -Duration <int>     Duration in seconds (5-8, default: 5)
  -AspectRatio <str>  Aspect ratio: 16:9 or 9:16 (default: 16:9)
  -Resolution <str>   Resolution: 720p, 1080p, 4k (default: 1080p)
  -Gpu <name>         Colab GPU (default: none / CPU)
  -Timeout <int>      Execution timeout in seconds (default: 1200)
"@
    exit 0
}

$ScriptDir = $PSScriptRoot
$Runner = Join-Path $ScriptDir "scripts\runner.py"

if (-not (Test-Path $Runner)) {
    Write-Error "Runner script not found: $Runner"
    exit 2
}

$argsList = @("single", "--prompt", $Prompt, "--model", $Model, "--duration", $Duration.ToString(), "--aspect-ratio", $AspectRatio, "--resolution", $Resolution, "--gpu", $Gpu, "--timeout", $Timeout.ToString())

foreach ($img in $Image) {
    $argsList += @("-i", $img)
}

if ($FirstFrame) {
    $argsList += @("--first-frame", $FirstFrame)
}
if ($LastFrame) {
    $argsList += @("--last-frame", $LastFrame)
}
if ($Output) {
    $argsList += @("-o", $Output)
}

python $Runner @argsList
