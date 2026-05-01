# Paper Harbor Skill

中文名：文献港

这是一个 Codex skill，用来按用户提示词从 Web of Science、ScienceDirect、中国知网三类站点检索文献，筛选候选文章，并把题名、DOI、期刊、年份、官方地址等元数据保存到 Zotero。当前版本不下载 PDF/HTML 全文。

## 安装依赖

```powershell
python -m pip install -r requirements.txt
```

核心约定：

- Web of Science 使用端口 `9224`
- ScienceDirect 使用端口 `9225`
- 中国知网/CNKI 使用端口 `9226`
- 用户自己在对应浏览器里登录，skill 不输入账号密码
- 输出目录按你给的截图创建
- 单次运行最多整理 `50` 篇，超过会自动按 50 篇封顶
- 不下载 PDF，不点击 View PDF、Download PDF 或下载完整期刊
- 不并发处理，一次只保存一条 Zotero 元数据
- 不绕过付费墙、验证码、权限限制、异常访问提醒或网站安全提示
- 对用户来说是一条完整流程：先自动保存候选文献的题名、地址、期刊、年份、影响因子字段等基本信息，再从候选清单中串行写入 Zotero
- 即使 Zotero 入库失败，也必须交付候选清单、文章地址、待处理清单和失败原因
- ScienceDirect 搜索结果页通常不直接提供影响因子；影响因子需来自 `内部数据_一般不用打开/journal_impact_factors.csv` 或其他可信来源，不能臆造
- 如果官方页面出现“下载完整期刊/Download full issue”，不要点击；Paper Harbor 只做元数据入库
- ScienceDirect 默认使用 Zotero Desktop 本地接口保存 metadata-only 条目，不请求 PDF 附件

推荐提示词模板：

```text
Use skill paper-harbor 帮我在“网站名”整理“关键词”的“时间限制”文献，“影响因子限制”，“篇数限制”，保存到 Zotero 并输出到“目录”
```

示例：

```text
Use skill paper-harbor 帮我在“ScienceDirect”整理“solid electrolyte interphase”的“2021-2026”文献，“影响因子大于5”，“先整理3篇”，保存到 Zotero 并输出到“.\runs\sei”
```

先创建一次输出目录试跑：

```powershell
python .\scripts\lit_download_assistant.py --site sciencedirect --keywords "gaussian cage catalysis" --year-from 2020 --year-to 2026 --if-min 5 --limit 10 --out ".\runs"
```

也可以把完整自然语言提示词写进文本文件后试跑：

```powershell
python .\scripts\lit_download_assistant.py --prompt-file .\examples\prompt_smoke_test.txt
```

检查端口是否打开：

```powershell
python .\scripts\browser_port_check.py --site sciencedirect
```

检查 Zotero 是否可用：

```powershell
python .\scripts\zotero_bridge.py doctor
```

如果 doctor 提示 `23119` 拒绝连接，第一次使用时先运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_zotero_setup.ps1
```

按官方页面安装 Zotero Desktop 和当前浏览器的 Zotero Connector，然后打开 Zotero Desktop，再重新运行 doctor。正式跑 ScienceDirect 时推荐：

```powershell
python .\scripts\sciencedirect_drission_run.py --port 9225 --query-file .\examples\current_sei_query.txt --year-from 2021 --year-to 2026 --if-min 5 --limit 3 --out ".\runs\sei-zotero"
```

运行时浏览器会打开候选文章页；脚本会把筛选出的文献元数据写入 Zotero，并同步更新 `已入库Zotero文献清单.csv`。不会下载 PDF。

## 开源与隐私说明

本仓库不包含账号、Cookie、PDF 文件、Zotero 数据库、下载结果或机构访问凭证。`runs/`、`已下载全文/`、`内部数据_一般不用打开/`、`.sqlite`、`.pdf`、`.csv` 等运行产物默认被 `.gitignore` 排除。

使用者必须自行登录数据库网站和 Zotero。Paper Harbor 不输入密码、不解决验证码、不绕过付费墙、不使用盗版镜像。

把整个 `literature-site-downloader-skill` 文件夹复制或放到 Codex skills 目录后，就可以用自然语言触发，例如：

```text
Use skill paper-harbor 帮我在“ScienceDirect”整理“solid electrolyte interphase”的“2021-2026”文献，“影响因子大于8”，“20篇”，保存到 Zotero 并输出到“.\runs\sei”
```
