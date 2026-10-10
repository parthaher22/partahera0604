$ErrorActionPreference = "Stop"
$base = "C:\Users\PARTH\OneDrive\Desktop\E-grampanchyat\backend"
$python = "$base\.venv\Scripts\python.exe"
$pidFile = "$base\uvicorn.pid"

# Stop any previous instance to free port 5000 before starting fresh.
if (Test-Path $pidFile) {
  $old = Get-Content $pidFile | Select-Object -First 1
  if ($old -and ($null -ne (Get-Process -Id $old -ErrorAction SilentlyContinue))) {
    Stop-Process -Id $old -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
  }
}

$proc = Start-Process -FilePath $python -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","5000" -WorkingDirectory $base -RedirectStandardOutput "$base\uvicorn.out.log" -RedirectStandardError "$base\uvicorn.err.log" -WindowStyle Hidden -PassThru
Set-Content -Path $pidFile -Value $proc.Id
Write-Output "started $($proc.Id)"