# Paper Harbor Skill

中文名：文献港

这是一个新的 Codex skill，用来按用户提示词从 Web of Science、ScienceDirect、中国知网三类站点检索文献，并在用户已经登录且有合法访问权限的情况下下载全文。

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
- 单次运行最多下载 `50` 篇，超过会自动按 50 篇封顶
- 优先下载开放获取或机构/账号明确可访问的全文
- 不并发下载，一次只处理一篇
- 不绕过付费墙、验证码、权限限制、异常访问提醒或网站安全提示
- 对用户来说是一条完整流程：先自动保存候选文献的题名、地址、期刊、年份、影响因子字段等基本信息，再从候选清单中串行尝试下载
- 即使下载失败，也必须交付候选清单、文章地址、待处理清单和失败原因
- ScienceDirect 搜索结果页通常不直接提供影响因子；影响因子需来自 `内部数据_一般不用打开/journal_impact_factors.csv` 或其他可信来源，不能臆造
- 如果官方页面出现“下载完整期刊/Download full issue”，只在弹窗可逐篇选择时使用：取消所有不符合条件的文章，只保留候选清单里的目标文章；如果不能逐篇取消，就不下载整期
- ScienceDirect 默认推荐使用 Zotero 辅助保存：Zotero Connector 在已登录浏览器中保存官方文章页，paper-harbor 只读 Zotero 本地库，把已保存的 PDF 附件复制到 `已下载全文`

推荐提示词模板：

```text
Use skill paper-harbor 帮我在“网站名”整理下载“关键词”的“时间限制”文献，“影响因子限制”，“篇数限制”，下载到“目录”
```

示例：

```text
Use skill paper-harbor 帮我在“ScienceDirect”整理下载“solid electrolyte interphase”的“2021-2026”文献，“影响因子大于5”，“先下载3篇”，下载到“.\runs\sei”
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
python .\scripts\sciencedirect_drission_run.py --port 9225 --query-file .\examples\current_sei_query.txt --year-from 2021 --year-to 2026 --if-min 5 --limit 3 --max-attempts 3 --download-method zotero --out ".\runs\sei-zotero"
```

运行时浏览器会打开候选文章页；看到提示后点击浏览器里的 Zotero Connector 按钮保存当前文章，脚本会等待 Zotero 生成 PDF 附件并复制到输出目录。

## 开源与隐私说明

本仓库不包含账号、Cookie、PDF 文件、Zotero 数据库、下载结果或机构访问凭证。`runs/`、`已下载全文/`、`内部数据_一般不用打开/`、`.sqlite`、`.pdf`、`.csv` 等运行产物默认被 `.gitignore` 排除。

使用者必须自行登录数据库网站和 Zotero。Paper Harbor 不输入密码、不解决验证码、不绕过付费墙、不使用盗版镜像。

把整个 `literature-site-downloader-skill` 文件夹复制或放到 Codex skills 目录后，就可以用自然语言触发，例如：

```text
Use skill paper-harbor 帮我在“ScienceDirect”整理下载“solid electrolyte interphase”的“2021-2026”文献，“影响因子大于8”，“20篇”，下载到“.\runs\sei”
```
