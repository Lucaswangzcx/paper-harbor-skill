param(
    [switch]$SkipOpen
)

$downloadUrl = "https://www.zotero.org/download/"
$connectorHelpUrl = "https://www.zotero.org/support/connector"

Write-Output "Paper Harbor first-use setup: Zotero"
Write-Output "1. Install Zotero Desktop from: $downloadUrl"
Write-Output "2. Install Zotero Connector for your default browser from the same download page."
Write-Output "3. Open Zotero Desktop and keep it running."
Write-Output "4. In the browser, pin or expose the Zotero Connector button."
Write-Output "5. Run: python .\scripts\zotero_bridge.py doctor"
Write-Output ""
Write-Output "Official Connector help: $connectorHelpUrl"

if (-not $SkipOpen) {
    Start-Process $downloadUrl
    Start-Process $connectorHelpUrl
}
