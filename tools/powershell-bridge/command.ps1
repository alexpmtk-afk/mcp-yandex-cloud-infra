$ErrorActionPreference = 'Continue'
Write-Host '=== MARKETPLACE_STOREFRONT_SMOKE_BEGIN ==='
Write-Host "RUNNER=$env:RUNNER_NAME"
Write-Host "COMPUTER=$env:COMPUTERNAME"
Write-Host "USER=$env:USERNAME"

$ozonUrl = 'https://www.ozon.ru/product/nippel-dlya-beskamernyh-shin-ventil-sosok-avtomobilnyy-rezinovyy-1420875699/'
$ozonHome = 'https://www.ozon.ru/'
$wbUrl = 'https://card.wb.ru/cards/v4/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm=178695806'

function Test-HttpUrl($name, $url) {
  try {
    $r = Invoke-WebRequest -Uri $url -Method Get -MaximumRedirection 5 -UseBasicParsing -TimeoutSec 30 -Headers @{
      'User-Agent'='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36'
      'Accept-Language'='ru-RU,ru;q=0.9,en;q=0.8'
    }
    Write-Host "$name`_HTTP=$([int]$r.StatusCode)"
    Write-Host "$name`_FINAL=$($r.BaseResponse.ResponseUri.AbsoluteUri)"
    Write-Host "$name`_LEN=$($r.Content.Length)"
    $preview = ($r.Content -replace '[\r\n]+',' ')
    if ($preview.Length -gt 240) { $preview = $preview.Substring(0,240) }
    Write-Host "$name`_PREVIEW=$preview"
  } catch {
    $status = $null
    try { $status = [int]$_.Exception.Response.StatusCode } catch {}
    Write-Host "$name`_HTTP=$status"
    Write-Host "$name`_ERROR=$($_.Exception.Message)"
  }
}

Test-HttpUrl 'OZON_HOME' $ozonHome
Test-HttpUrl 'OZON_PRODUCT' $ozonUrl
Test-HttpUrl 'WB_V4' $wbUrl

$browserCandidates = @(
  @{Name='ChromeProgramFiles'; Path='C:\Program Files\Google\Chrome\Application\chrome.exe'},
  @{Name='ChromeX86'; Path='C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'},
  @{Name='ChromeUser'; Path='C:\Users\Win10_Game_OS\AppData\Local\Google\Chrome\Application\chrome.exe'},
  @{Name='YandexUser'; Path='C:\Users\Win10_Game_OS\AppData\Local\Yandex\YandexBrowser\Application\browser.exe'},
  @{Name='YandexProgramFiles'; Path='C:\Program Files (x86)\Yandex\YandexBrowser\Application\browser.exe'}
)
$browser = $browserCandidates | Where-Object { Test-Path $_.Path } | Select-Object -First 1
if ($browser) {
  Write-Host "BROWSER_NAME=$($browser.Name)"
  Write-Host "BROWSER_PATH=$($browser.Path)"
  try {
    $ver = (Get-Item $browser.Path).VersionInfo.ProductVersion
    Write-Host "BROWSER_VERSION=$ver"
  } catch {}

  $profile = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\ozon-anon-profile-smoke'
  New-Item -ItemType Directory -Force -Path $profile | Out-Null
  $dump = Join-Path $env:RUNNER_TEMP 'ozon-dump.txt'
  $args = @(
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    "--user-data-dir=$profile",
    '--lang=ru-RU',
    '--dump-dom',
    $ozonUrl
  )
  try {
    $p = Start-Process -FilePath $browser.Path -ArgumentList $args -NoNewWindow -RedirectStandardOutput $dump -RedirectStandardError (Join-Path $env:RUNNER_TEMP 'ozon-browser-err.txt') -PassThru
    if (-not $p.WaitForExit(60000)) { $p.Kill(); Write-Host 'BROWSER_TIMEOUT=YES' }
    Write-Host "BROWSER_EXIT=$($p.ExitCode)"
    if (Test-Path $dump) {
      $content = Get-Content $dump -Raw -ErrorAction SilentlyContinue
      Write-Host "BROWSER_DOM_LEN=$($content.Length)"
      $signals = @('Похоже, нет соединения','Нам нужно убедиться, что вы не робот','Antibot','1420875699','₽','руб')
      foreach ($s in $signals) { Write-Host ("BROWSER_SIGNAL_{0}={1}" -f ($s -replace '[^A-Za-z0-9А-Яа-я]','_'), [bool]($content -match [regex]::Escape($s))) }
      $title = [regex]::Match($content,'<title[^>]*>(.*?)</title>','IgnoreCase,Singleline').Groups[1].Value
      if ($title) { Write-Host "BROWSER_TITLE=$title" }
    }
  } catch {
    Write-Host "BROWSER_ERROR=$($_.Exception.Message)"
  }
} else {
  Write-Host 'BROWSER_FOUND=NO'
}

Write-Host '=== MARKETPLACE_STOREFRONT_SMOKE_END ==='
