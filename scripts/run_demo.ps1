param(
  [Parameter(Mandatory = $true)]
  [string]$Python,

  [Parameter(Mandatory = $true)]
  [string]$OutputDir,

  [string]$Config = "",
  [string]$ExternalSkillRoot = "",
  [switch]$BackupAndReplaceSkills
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$PythonCommand = if (Test-Path -LiteralPath $Python) {
  (Resolve-Path -LiteralPath $Python).Path
} else {
  (Get-Command $Python -ErrorAction Stop).Source
}

if (-not $Config) {
  $Config = Join-Path $RepositoryRoot "examples\deckcompiler_demo\demo.yaml"
}
if (-not $ExternalSkillRoot) {
  if ($env:DECKCOMPILER_EXTERNAL_SKILLS) {
    $ExternalSkillRoot = $env:DECKCOMPILER_EXTERNAL_SKILLS
  } elseif ($env:CODEX_HOME) {
    $ExternalSkillRoot = Join-Path $env:CODEX_HOME "skills"
  } else {
    $ExternalSkillRoot = Join-Path ([Environment]::GetFolderPath("UserProfile")) ".codex\skills"
  }
}

$Installer = Join-Path $RepositoryRoot "scripts\install_pngtopptx_skillset.py"
$InstallerArguments = @(
  $Installer,
  "--target-root",
  $ExternalSkillRoot
)
if ($BackupAndReplaceSkills) {
  $InstallerArguments += "--backup-and-replace"
}

& $PythonCommand @InstallerArguments
if ($LASTEXITCODE -ne 0) {
  throw "CAPTW/pngtopptx automatic installation failed with exit code $LASTEXITCODE."
}

$env:PYTHONPATH = Join-Path $RepositoryRoot "src"
$env:PYTHONNOUSERSITE = "1"
$env:DECKCOMPILER_EXTERNAL_SKILLS = $ExternalSkillRoot

& $PythonCommand -B -m presentation_agent.deckcompiler demo `
  --config $Config `
  --output-dir $OutputDir
exit $LASTEXITCODE
