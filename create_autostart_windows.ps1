# ------------------------------
# Detect real python.exe
# ------------------------------

$possibleRoots = @(
    "$env:LOCALAPPDATA\Programs\Python",
    "C:\Python",
    "C:\Python*",
    "C:\Program Files\Python*",
    "C:\Program Files (x86)\Python*"
)

$python = $null

foreach ($root in $possibleRoots) {

    $paths = Get-ChildItem -Path $root -Recurse -Filter python.exe -ErrorAction SilentlyContinue |
                Select-Object -First 1

    if ($paths) {
        $python = $paths.FullName
        break
    }
}

if (-not $python) {
    Write-Host "ERROR: Real Python not found. Install Python from python.org (not Microsoft Store)."
    exit 1
}

Write-Host "Detected Python at: $python"


# ------------------------------
# Path to your script
# ------------------------------
$script = "C:\system\metrix\metrix_server.py"

# ------------------------------
# Build Task Scheduler entry
# ------------------------------
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`""
$trigger = New-ScheduledTaskTrigger -AtLogon
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# Register the task
Register-ScheduledTask -TaskName "MetrixServerAutostart" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Metrix server autostart" `
    -RunLevel Limited `
    -Force

Write-Host "Windows autostart installed successfully."
