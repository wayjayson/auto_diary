<#
.SYNOPSIS
    Registers (or updates) a Windows Task Scheduler job that runs
    auto_dairy every day at the time specified in .env (SCHEDULE_TIME).

.DESCRIPTION
    * Reads SCHEDULE_TIME from the .env file in the same directory.
    * Creates a scheduled task named "auto_dairy_daily".
    * The task runs as the current user (no password required for
      interactive logon sessions).
    * Run this script once after initial setup; re-run it any time
      you change SCHEDULE_TIME.

.NOTES
    Requires Windows PowerShell 5.1+ or PowerShell 7+.
    Must be run as Administrator the first time to register the task.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Locate the project root (same folder as this script) ─────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile   = Join-Path $ScriptDir ".env"
$MainScript = Join-Path $ScriptDir "diary_generator.py"

if (-not (Test-Path $EnvFile)) {
    Write-Error ".env file not found at '$EnvFile'. Please copy .env.example to .env first."
    exit 1
}

if (-not (Test-Path $MainScript)) {
    Write-Error "diary_generator.py not found at '$MainScript'."
    exit 1
}

# ── Parse SCHEDULE_TIME from .env ────────────────────────────────────────────
$ScheduleTime = "23:00"   # default
foreach ($line in Get-Content $EnvFile) {
    $line = $line.Trim()
    if ($line -match '^\s*SCHEDULE_TIME\s*=\s*(.+)\s*$') {
        $ScheduleTime = $Matches[1].Trim()
        break
    }
}

# Validate HH:MM format
if ($ScheduleTime -notmatch '^\d{2}:\d{2}$') {
    Write-Error "Invalid SCHEDULE_TIME '$ScheduleTime' in .env. Expected HH:MM (e.g. 23:00)."
    exit 1
}

Write-Host "Configuring scheduled task to run daily at $ScheduleTime ..."

# ── Locate Python ─────────────────────────────────────────────────────────────
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue)?.Source
if (-not $PythonExe) {
    Write-Error "Python not found on PATH. Please install Python 3.10+ and add it to PATH."
    exit 1
}
Write-Host "Using Python: $PythonExe"

# ── Build Task Scheduler objects ──────────────────────────────────────────────
$TaskName   = "auto_dairy_daily"
$TaskAction = New-ScheduledTaskAction `
    -Execute  $PythonExe `
    -Argument "`"$MainScript`"" `
    -WorkingDirectory $ScriptDir

$hour, $minute = $ScheduleTime -split ':'
$TriggerTime = [datetime]::Today.AddHours([int]$hour).AddMinutes([int]$minute)
$TaskTrigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime

$TaskSettings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# ── Register or update the task ───────────────────────────────────────────────
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Set-ScheduledTask -TaskName $TaskName `
        -Action   $TaskAction `
        -Trigger  $TaskTrigger `
        -Settings $TaskSettings | Out-Null
    Write-Host "Updated existing scheduled task '$TaskName'."
} else {
    Register-ScheduledTask -TaskName $TaskName `
        -Action   $TaskAction `
        -Trigger  $TaskTrigger `
        -Settings $TaskSettings `
        -RunLevel Highest | Out-Null
    Write-Host "Registered new scheduled task '$TaskName'."
}

Write-Host ""
Write-Host "✅  auto_dairy will run every day at $ScheduleTime."
Write-Host "    To view/edit: open Task Scheduler and look for '$TaskName'."
Write-Host "    To remove:    Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
