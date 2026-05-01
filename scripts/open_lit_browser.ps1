param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("sciencedirect", "cnki")]
  [string]$Site
)

$sites = @{
  "sciencedirect" = @{
    Port = 9225
    Url = "https://www.sciencedirect.com/search"
    Profile = "sciencedirect"
  }
  "cnki" = @{
    Port = 9226
    Url = "https://www.cnki.net/"
    Profile = "cnki"
  }
}

function Get-DefaultBrowserPath {
  $userChoice = "Registry::HKEY_CURRENT_USER\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
  $progId = (Get-ItemProperty -Path $userChoice -ErrorAction Stop).ProgId
  $commandPath = "Registry::HKEY_CLASSES_ROOT\$progId\shell\open\command"
  $command = (Get-ItemProperty -Path $commandPath -ErrorAction Stop)."(default)"
  if ($command -match '"([^"]+\.exe)"') {
    return $matches[1]
  }
  if ($command -match '^([^\s]+\.exe)') {
    return $matches[1]
  }
  throw "Cannot parse default browser command: $command"
}

$config = $sites[$Site]
$browser = Get-DefaultBrowserPath
$profile = Join-Path $env:LOCALAPPDATA "CodexLitProfiles\$($config.Profile)"
New-Item -ItemType Directory -Force $profile | Out-Null

Write-Host "Opening default browser:"
Write-Host $browser
Write-Host "Remote debugging port: $($config.Port)"
Write-Host "Profile: $profile"
Write-Host "Reminder: after the site opens, sign in to the site and EasyScholar in this same default browser profile."

Start-Process -FilePath $browser -ArgumentList @(
  "--remote-debugging-port=$($config.Port)",
  "--user-data-dir=$profile",
  $config.Url
)
