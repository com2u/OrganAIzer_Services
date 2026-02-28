Start-Sleep -Seconds 3
$url = "http://localhost:8000/docs"
try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
    Write-Host "Backend UP: $($r.StatusCode)"
} catch {
    Write-Host "Backend NOT running. Starting it now..."
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k cd /d c:\Users\rxhec\OrganAIzer_Services\backend && python main.py"
    Write-Host "Backend start command issued. Wait 10 seconds then run test_agent_live.ps1"
}
