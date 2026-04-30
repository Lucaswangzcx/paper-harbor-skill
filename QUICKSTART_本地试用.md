# Paper Harbor 本地试用步骤

推荐提示词：

```text
Use skill paper-harbor 帮我在“网站名”整理下载“关键词”的“时间限制”文献，“影响因子限制”，“篇数限制”，下载到“目录”
```

## 1. 先生成一次输出目录

在当前目录打开 PowerShell：

```powershell
cd C:\path\to\paper-harbor-skill
python .\scripts\lit_download_assistant.py --site sciencedirect --keywords "solid electrolyte interphase" --year-from 2021 --year-to 2026 --if-min 5 --limit 10 --out .\runs
```

如果关键词有空格，请保留英文双引号。

也可以直接用提示词文件测试模板解析：

```powershell
python .\scripts\lit_download_assistant.py --prompt-file .\examples\prompt_smoke_test.txt
```

脚本会生成类似目录：

```text
runs\20260429_211000_sciencedirect_solid_electrolyte_interphase\
```

里面包含：

```text
00_先看我_文件说明.txt
README_先看我.md
下载报告.pdf
下载报告.html
文章地址总表.csv
候选文献总表.csv
高优先级文献.csv
中优先级文献.csv
低优先级文献.csv
已下载文献清单.csv
待处理文献清单.csv
检索计划.md
已下载全文\
内部数据_一般不用打开\
```

## 2. 打开对应网站的登录浏览器

三选一即可。第一次建议先用 ScienceDirect。

默认使用 Windows 当前默认浏览器，并带上对应远程调试端口。默认浏览器需要是 Chrome 或 Edge 这类 Chromium 浏览器，否则远程调试端口可能不可用。

### Web of Science

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_lit_browser.ps1 -Site wos
```

### ScienceDirect

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_lit_browser.ps1 -Site sciencedirect
```

### 中国知网/CNKI

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_lit_browser.ps1 -Site cnki
```

在弹出的浏览器里手动登录。Codex 不会输入账号、密码、验证码。

## 3. 检查端口是否连上

登录完成后运行：

```powershell
python .\scripts\browser_port_check.py --site sciencedirect
```

看到类似下面内容就说明端口通了：

```text
OK: ScienceDirect browser debugging port 9225 is reachable.
```

## 4. 回到 Codex 继续

告诉 Codex：

```text
我已经在 9225 登录 ScienceDirect 了。请用 paper-harbor 继续测试，关键词是 solid electrolyte interphase，2021-2026，影响因子大于 5，先下载 3 篇，输出目录用刚才 runs 里生成的目录。
```

## 5. 第一次使用：安装并打开 Zotero

ScienceDirect 的 PDF 预览页有时不暴露可自动点击的保存按钮。推荐把 Zotero 作为官方页面保存器：

第一次使用时，先运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_zotero_setup.ps1
```

然后按页面提示：

1. 安装 Zotero Desktop。
2. 安装默认浏览器的 Zotero Connector。
3. 打开 Zotero Desktop 并保持运行。
4. 在浏览器里把 Zotero Connector 按钮固定/显示出来。
5. 运行：

```powershell
python .\scripts\zotero_bridge.py doctor
```

如果能看到 `zotero_connector_reachable.ok: true` 且有 `zotero_sqlite` 路径，就可以用 Zotero 辅助下载。

## 完整流程：先保存候选，再尝试下载

用户侧只需要一句提示词，skill 内部会先保存候选清单，再尝试下载。即使下载失败，也会保留筛选出的候选信息和失败原因。

完整运行：

```powershell
python .\scripts\sciencedirect_drission_run.py --port 9225 --query-file .\examples\current_sei_query.txt --year-from 2021 --year-to 2026 --if-min 5 --limit 3 --max-attempts 3 --download-method zotero --out ".\runs\sciencedirect_sei_2021_2026"
```

下载阶段的优先策略：

1. 默认打开官方文章页，并等待你点击 Zotero Connector 保存当前文章。
2. Zotero 保存成功后，脚本只读 Zotero 本地库，把 PDF 附件复制到 `已下载全文`。
3. 如果官方页面有 `下载完整期刊` / `Download full issue`，只在弹窗可逐篇选择时使用，并取消所有无关文章。
4. 如果 Zotero 没有保存 PDF 附件，或页面不允许保存全文，写入 `待处理文献清单.csv`。
5. 每篇完成后更新 `已下载文献清单.csv` 或 `待处理文献清单.csv`。

## 强制规则

这些规则不能被用户提示词覆盖：

- 单次运行最多下载 50 篇。
- 优先下载开放获取或机构/账号明确可访问的全文。
- 不并发下载，一次只处理一篇。
- 不绕过付费墙、验证码、权限限制、异常访问提醒或网站安全提示。
- 权限不清楚、需要付费、需要验证码、或访问失败的文献，写入 `待处理文献清单.csv`。
