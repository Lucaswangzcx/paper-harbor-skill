# Install

把这个文件夹安装到 Codex skills 目录，建议安装目录叫 `paper-harbor`：

```powershell
$src = "C:\path\to\paper-harbor-skill"
$dst = "$env:USERPROFILE\.codex\skills\paper-harbor"
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item -Recurse -Force "$src\*" $dst
```

然后重启 Codex 或开启新会话。之后可以这样试：

```text
Use skill paper-harbor 帮我在“ScienceDirect”整理下载“solid electrolyte interphase”的“2021-2026”文献，“影响因子大于5”，“10篇”，下载到“.\runs\sei”
```

第一次真正下载前，先打开对应网站端口浏览器并登录：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_lit_browser.ps1 -Site sciencedirect
```

第一次使用推荐先安装 Zotero Desktop 和默认浏览器的 Zotero Connector：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_zotero_setup.ps1
```

安装完成后打开 Zotero Desktop，并检查：

```powershell
python .\scripts\zotero_bridge.py doctor
```

ScienceDirect 推荐用 Zotero 辅助模式：

```powershell
python .\scripts\sciencedirect_drission_run.py --port 9225 --query-file .\examples\current_sei_query.txt --year-from 2021 --year-to 2026 --if-min 5 --limit 3 --max-attempts 3 --download-method zotero --out ".\runs\sei-zotero"
```

强制规则：

- 单次运行最多下载 `50` 篇。
- 优先下载开放获取或机构/账号明确可访问全文。
- 不并发下载。
- 不绕过付费墙、验证码、权限限制、异常访问提醒或网站安全提示。
