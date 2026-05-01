# Paper Harbor Skill

Paper Harbor 是一个 Codex skill，用来从 Web of Science、ScienceDirect 和知网整理文献信息，并把筛选后的条目保存到 Zotero。

它现在不是下载器。它不会点 PDF 下载、不会下载整期、不会处理验证码、不会绕过付费墙，也不会去找非官方来源。它做的事情很简单：检索、记录、生成表格、把元数据放进 Zotero。

## 能做什么

- 用你已经登录好的浏览器检索文献网站。
- 记录题名、期刊、年份、DOI、文章地址、访问状态等信息。
- 生成候选表、地址表、高中低优先级表。
- 把符合条件的文献作为 metadata-only 条目保存到 Zotero。
- 如果某条文献无法处理，会写进待处理清单，不会悄悄跳过。

默认端口：

| 网站 | 端口 |
|---|---:|
| Web of Science | `9224` |
| ScienceDirect | `9225` |
| 知网/CNKI | `9226` |

## 安装依赖

```powershell
python -m pip install -r requirements.txt
```

把这个文件夹安装到 Codex skills 目录，技能名建议用 `paper-harbor`。安装后重启 Codex，或者开启一个新会话。

## 第一次使用

先打开 Zotero Desktop，然后检查本地接口：

```powershell
python .\scripts\zotero_bridge.py doctor
```

如果 Zotero 还没装好，可以运行这个脚本打开官方安装页面：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_zotero_setup.ps1
```

然后打开对应网站的浏览器窗口并手动登录。比如 ScienceDirect：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_lit_browser.ps1 -Site sciencedirect
python .\scripts\browser_port_check.py --site sciencedirect
```

## 用法示例

自然语言触发：

```text
Use skill paper-harbor 帮我在“ScienceDirect”整理“solid electrolyte interphase”的“2021-2026”文献，“影响因子大于5”，“先整理25篇”，保存到 Zotero 并输出到“D:\papers\sei”
```

也可以直接跑脚本。

先创建输出目录：

```powershell
python .\scripts\lit_download_assistant.py --site sciencedirect --keywords "solid electrolyte interphase" --year-from 2021 --year-to 2026 --if-min 5 --limit 25 --out ".\runs"
```

确认 `9225` 浏览器已经登录后，开始整理并入库 Zotero：

```powershell
python .\scripts\sciencedirect_drission_run.py --port 9225 --query "solid electrolyte interphase" --year-from 2021 --year-to 2026 --if-min 5 --limit 25 --out ".\runs\sei"
```

## 输出目录

一次运行会生成类似这样的目录：

```text
00_先看我_文件说明.txt
README_先看我.md
检索计划.md
文献整理报告.html
文章地址总表.csv
候选文献总表.csv
高优先级文献.csv
中优先级文献.csv
低优先级文献.csv
已入库Zotero文献清单.csv
待处理文献清单.csv
内部数据_一般不用打开/
```

主要看两个文件：

- `已入库Zotero文献清单.csv`：已经保存到 Zotero 的条目。
- `待处理文献清单.csv`：没有成功处理、需要人工确认的条目。

## 关于影响因子

ScienceDirect 这类页面通常不会直接给影响因子，所以 Paper Harbor 不会自己编一个。

如果需要按影响因子筛选，可以放一个可信来源的表到：

```text
内部数据_一般不用打开/journal_impact_factors.csv
```

推荐表头：

```csv
journal,issn,eissn,impact_factor,year,source,notes
```

没有这个表时，skill 仍然会整理文献并保存到 Zotero，只是不会把“影响因子大于 5”当成已经核验过的条件。

## 隐私和边界

这个仓库不包含账号、Cookie、Zotero 数据库、PDF、运行结果、浏览器 profile 或机构访问凭证。`runs/`、`内部数据_一般不用打开/`、`.sqlite`、`.pdf`、`.csv` 等运行产物默认不会进仓库。

使用者自己登录网站和 Zotero。Paper Harbor 不输入密码，不解验证码，不绕过权限，也不从非官方来源获取论文。
