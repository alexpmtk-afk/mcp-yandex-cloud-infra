$ErrorActionPreference = 'Continue'
Write-Host '=== OZON_YANDEX_DIRECT_TEST_BEGIN ==='
Write-Host "RUNNER=$env:RUNNER_NAME"
Write-Host "COMPUTER=$env:COMPUTERNAME"

$ozonUrl = 'https://www.ozon.ru/product/nippel-dlya-beskamernyh-shin-ventil-sosok-avtomobilnyy-rezinovyy-1420875699/'
$yandexCandidates = @(
  'C:\Users\Win10_Game_OS\AppData\Local\Yandex\YandexBrowser\Application\browser.exe',
  'C:\Program Files (x86)\Yandex\YandexBrowser\Application\browser.exe',
  'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
)
$browser = $yandexCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) { Write-Host 'YANDEX_FOUND=NO'; exit 2 }
Write-Host "YANDEX_PATH=$browser"
Write-Host "YANDEX_VERSION=$((Get-Item $browser).VersionInfo.ProductVersion)"

try {
  $ip = Invoke-RestMethod -Uri 'https://api.ipify.org' -TimeoutSec 20
  Write-Host "SERVICE_PUBLIC_IP=$ip"
} catch { Write-Host "SERVICE_PUBLIC_IP_ERROR=$($_.Exception.Message)" }

Write-Host '=== WINHTTP_PROXY ==='
& netsh winhttp show proxy

$profile = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\ozon-yandex-anon-profile-smoke'
New-Item -ItemType Directory -Force -Path $profile | Out-Null
$dump = Join-Path $env:RUNNER_TEMP 'ozon-yandex-dump.txt'
$err = Join-Path $env:RUNNER_TEMP 'ozon-yandex-err.txt'
$args = @('--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',"--user-data-dir=$profile",'--lang=ru-RU','--dump-dom',$ozonUrl)
try {
  $p = Start-Process -FilePath $browser -ArgumentList $args -NoNewWindow -RedirectStandardOutput $dump -RedirectStandardError $err -PassThru
  if (-not $p.WaitForExit(60000)) { $p.Kill(); Write-Host 'YANDEX_TIMEOUT=YES' }
  Write-Host "YANDEX_EXIT=$($p.ExitCode)"
  if (Test-Path $dump) {
    $content = Get-Content $dump -Raw -ErrorAction SilentlyContinue
    Write-Host "YANDEX_DOM_LEN=$($content.Length)"
    Write-Host "YANDEX_HAS_SKU=$([bool]($content -match '1420875699'))"
    Write-Host "YANDEX_HAS_ANTIBOT=$([bool]($content -match 'Antibot|fab_chlg|__rr=1|incidentId'))"
    Write-Host "YANDEX_HAS_PRICE_MARKUP=$([bool]($content -match 'price|currency|RUB|rub'))"
    $m = [regex]::Match($content,'<title[^>]*>(.*?)</title>',[System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Singleline)
    if ($m.Success) { Write-Host "YANDEX_TITLE=$($m.Groups[1].Value)" }
    $out = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\ozon-yandex-smoke-dom.html'
    [IO.File]::WriteAllText($out,$content,(New-Object Text.UTF8Encoding($false)))
    Write-Host "YANDEX_DOM_SAVED=$out"
  }
  if (Test-Path $err) {
    $e = Get-Content $err -Raw -ErrorAction SilentlyContinue
    Write-Host "YANDEX_ERR_LEN=$($e.Length)"
    if ($e.Length -gt 0) { $ep=($e -replace '[\r\n]+',' '); if($ep.Length -gt 300){$ep=$ep.Substring(0,300)}; Write-Host "YANDEX_ERR_PREVIEW=$ep" }
  }
} catch { Write-Host "YANDEX_ERROR=$($_.Exception.Message)"; exit 3 }
Write-Host '=== OZON_YANDEX_DIRECT_TEST_END ==='
