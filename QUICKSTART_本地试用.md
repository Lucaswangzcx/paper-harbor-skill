# Paper Harbor 本地试用

Paper Harbor 现在是文献元数据整理和 Zotero 入库 skill，不下载 PDF/HTML 全文。

推荐提示词：

```text
Use skill paper-harbor 帮我在“ScienceDirect”整理“solid electrolyte interphase”的“2021-2026”文献，“影响因子大于5”，“先整理3篇”，保存到 Zotero 并输出到“.\runs\sei”
```

## 第一次使用

1. 打开 Zotero Desktop，并保持运行。
2. 打开对应网站端口浏览器并手动登录。
3. 不让 Codex 输入密码，不处理验证码，不绕过限制。

ScienceDirect：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_lit_browser.ps1 -Site sciencedirect
python .\scripts\browser_port_check.py --site sciencedirect
python .\scripts\zotero_bridge.py doctor
```

## 创建输出目录

```powershell
python .\scripts\lit_download_assistant.py --site sciencedirect --keywords "solid electrolyte interphase" --year-from 2021 --year-to 2026 --if-min 5 --limit 3 --out ".\runs"
```

输出目录会包含：

```text
候选文献总表.csv
文章地址总表.csv
高优先级文献.csv
中优先级文献.csv
低优先级文献.csv
已入库Zotero文献清单.csv
已下载文献清单.csv
待处理文献清单.csv
下载报告.html
检索计划.md
内部数据_一般不用打开/
```

`已下载文献清单.csv` 保留为空表，用于兼容旧输出结构；正常结果看 `已入库Zotero文献清单.csv`。

## ScienceDirect 真实运行

确认 9225 和 Zotero 都正常后：

```powershell
python .\scripts\sciencedirect_drission_run.py --port 9225 --query-file .\examples\current_sei_query.txt --year-from 2021 --year-to 2026 --if-min 5 --limit 3 --out ".\runs\sei-zotero"
```

运行逻辑：

1. 官方 ScienceDirect 页面检索。
2. 保存候选清单和文章地址。
3. 逐条打开官方文章页补充 DOI 等元数据。
4. 通过 Zotero Desktop 本地接口保存 metadata-only journalArticle 条目。
5. 不点击 View PDF、Download PDF、Download full issue，也不保存 PDF 预览页。

如果遇到验证码、机器人验证、权限警告或 Zotero 不可用，条目会进入 `待处理文献清单.csv`，候选信息不会丢失。
