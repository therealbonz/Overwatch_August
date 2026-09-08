# Run therealbonz.com Homepage & CMS locally
$backendDir = Join-Path $PSScriptRoot "backend"
Set-Location $backendDir

$python = "C:\Users\Brendhann\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Starting therealbonz.com Homepage & CMS on http://127.0.0.1:8080" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

& $python -m pip install -q -r requirements.txt
& $python -m uvicorn main:app --host 127.0.0.1 --port 8080 --reload
