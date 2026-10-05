# PowerShell install script for veo3.1-colab skill (supports Gemini CLI, Codex, and Antigravity)
param (
    [string]$Target = "",
    [switch]$Gemini,
    [switch]$Codex,
    [switch]$All,
    [string]$Dest,
    [switch]$Force,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host @"
Install the Google Veo 3.1 Colab skill into Gemini CLI and/or Codex skills directory.

Usage:
  .\install.ps1 [-Target <gemini|codex|all>] [-Force]
  .\install.ps1 [-Gemini] [-Codex] [-All] [-Force]
  .\install.ps1 [-Dest <SKILLS_DIR>] [-Force]

Targets:
  -Gemini, -Target gemini  Install to Gemini CLI (~/.gemini/skills) [Default]
  -Codex,  -Target codex   Install to Codex (~/.codex/skills)
  -All,    -Target all     Install to both Gemini CLI and Codex
  -Dest <PATH>             Custom skills directory

Options:
  -Force                   Replace an existing install after creating a timestamped backup
  -Help                    Show this help
"@
    exit 0
}

$SkillName = "veo3.1-colab"
$RepoDir = $PSScriptRoot

# Check required files
$requiredFiles = @("SKILL.md", "scripts\runner.py", "assets\Veo_3_1_Colab.ipynb")
foreach ($req in $requiredFiles) {
    $fullPath = Join-Path $RepoDir $req
    if (-not (Test-Path $fullPath)) {
        Write-Error "Repository is missing required file: $req"
        exit 2
    }
}

function Install-ToDirectory([string]$skillsRoot, [string]$label) {
    if (-not (Test-Path $skillsRoot)) {
        New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null
    }

    $targetPath = Join-Path $skillsRoot $SkillName
    $backupPath = ""

    if (Test-Path $targetPath) {
        if (-not $Force) {
            Write-Host "[$label] Skill already installed; preserving: $targetPath"
            Write-Host "       Use -Force to replace it (the old directory will be backed up)."
            return
        }
        $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
        $backupPath = "$targetPath.backup.$timestamp"
        $suffix = 0
        while (Test-Path $backupPath) {
            $suffix++
            $backupPath = "$targetPath.backup.$timestamp.$suffix"
        }
        Move-Item -Path $targetPath -Destination $backupPath
    }

    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("veo_install_" + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

    try {
        Copy-Item -Path (Join-Path $RepoDir "SKILL.md") -Destination (Join-Path $tempDir "SKILL.md") -Force
        Copy-Item -Path (Join-Path $RepoDir "scripts") -Destination (Join-Path $tempDir "scripts") -Recurse -Force
        Copy-Item -Path (Join-Path $RepoDir "assets") -Destination (Join-Path $tempDir "assets") -Recurse -Force

        # Clean __pycache__
        Get-ChildItem -Path $tempDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

        Move-Item -Path $tempDir -Destination $targetPath
    } catch {
        if ($backupPath -and (-not (Test-Path $targetPath))) {
            Move-Item -Path $backupPath -Destination $targetPath
        }
        if (Test-Path $tempDir) {
            Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        Write-Error "[$label] Could not install skill at: $targetPath. Details: $_"
        return
    }

    Write-Host "[$label] Installed $SkillName to: $targetPath"
    if ($backupPath) {
        Write-Host "       Previous installation preserved at: $backupPath"
    }
}

if ($Dest) {
    Install-ToDirectory -skillsRoot ([System.IO.Path]::GetFullPath($Dest)) -label "Custom"
    exit 0
}

# Determine target
$chosenTarget = "gemini"
if ($All -or ($Target -eq "all")) {
    $chosenTarget = "all"
} elseif ($Codex -or ($Target -eq "codex")) {
    $chosenTarget = "codex"
} elseif ($Gemini -or ($Target -eq "gemini")) {
    $chosenTarget = "gemini"
}

$geminiSkills = if ($env:GEMINI_HOME) { Join-Path $env:GEMINI_HOME "skills" } else { Join-Path $env:USERPROFILE ".gemini\skills" }
$codexSkills  = if ($env:CODEX_HOME)  { Join-Path $env:CODEX_HOME "skills"  } else { Join-Path $env:USERPROFILE ".codex\skills" }

switch ($chosenTarget) {
    "gemini" {
        Install-ToDirectory -skillsRoot $geminiSkills -label "Gemini CLI"
    }
    "codex" {
        Install-ToDirectory -skillsRoot $codexSkills -label "Codex"
    }
    "all" {
        Install-ToDirectory -skillsRoot $geminiSkills -label "Gemini CLI"
        Install-ToDirectory -skillsRoot $codexSkills -label "Codex"
    }
}

# Auto-patch google-colab-cli for Windows if installed
$patchScript = Join-Path $RepoDir "scripts\patch_colab_cli.py"
if (Test-Path $patchScript) {
    try {
        & python $patchScript
    } catch {}
}
