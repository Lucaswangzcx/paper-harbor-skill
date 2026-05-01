param(
    [switch]$SkipOpen
)

$downloadUrl = "https://www.zotero.org/download/"
$connectorHelpUrl = "https://www.zotero.org/support/connector"
$easyScholarUrl = "https://chromewebstore.google.com/detail/easyscholar/njgedjcccpcfmjecccaajkjiphpddfji"
$easyScholarHomeUrl = "https://www.easyscholar.cc/"

Write-Output "Paper Harbor first-use setup: Zotero + EasyScholar"
Write-Output "1. Install Zotero Desktop from: $downloadUrl"
Write-Output "2. Install Zotero Connector for your default browser from the same download page."
Write-Output "3. Install EasyScholar in the same browser profile used for the literature site."
Write-Output "4. If EasyScholar asks for sign-in, complete it and refresh the ScienceDirect results page until IF badges appear."
Write-Output "5. Open Zotero Desktop and keep it running."
Write-Output "6. In Zotero, create/select collections such as: science direct, web of science, 中国知网."
Write-Output "7. In the browser, pin or expose Zotero Connector and EasyScholar."
Write-Output "8. Run: python .\scripts\zotero_bridge.py doctor"
Write-Output ""
Write-Output "Official Connector help: $connectorHelpUrl"
Write-Output "EasyScholar Chrome Web Store: $easyScholarUrl"
Write-Output "EasyScholar home: $easyScholarHomeUrl"

if (-not $SkipOpen) {
    Start-Process $downloadUrl
    Start-Process $connectorHelpUrl
    Start-Process $easyScholarUrl
    Start-Process $easyScholarHomeUrl
}
