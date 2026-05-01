# Paper Harbor Skill

Paper Harbor is a Codex skill for collecting literature metadata from Web of Science, ScienceDirect, and CNKI, then saving the selected records into Zotero.

It is not a PDF downloader. The skill does not click PDF buttons, download full issues, solve CAPTCHAs, bypass paywalls, or use unofficial mirrors. It keeps the workflow focused on search results, article pages, CSV reports, and Zotero metadata records.

## What It Does

- Searches one of the supported literature sites through a browser session you logged into yourself.
- Collects article title, journal, year, DOI, URL, access signal, and related notes.
- Saves candidate tables and priority lists as CSV files.
- Imports matching records into Zotero as metadata-only journal article items.
- Keeps failed or blocked records in a pending CSV instead of hiding them.

Supported browser debug ports:

| Site | Port |
|---|---:|
| Web of Science | `9224` |
| ScienceDirect | `9225` |
| CNKI | `9226` |

## Install

```powershell
python -m pip install -r requirements.txt
```

Install this folder as a Codex skill named `paper-harbor`, then restart Codex or start a new session.

## First-Time Setup

Open Zotero Desktop before running an import:

```powershell
python .\scripts\zotero_bridge.py doctor
```

If Zotero is not ready, this helper opens the official Zotero setup pages:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_zotero_setup.ps1
```

Then open the site browser profile and log in manually. For ScienceDirect:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_lit_browser.ps1 -Site sciencedirect
python .\scripts\browser_port_check.py --site sciencedirect
```

## Prompt Example

```text
Use skill paper-harbor 帮我在“ScienceDirect”整理“solid electrolyte interphase”的“2021-2026”文献，“影响因子大于5”，“先整理25篇”，保存到 Zotero 并输出到“D:\papers\sei”
```

## Script Example

Create an output folder:

```powershell
python .\scripts\lit_download_assistant.py --site sciencedirect --keywords "solid electrolyte interphase" --year-from 2021 --year-to 2026 --if-min 5 --limit 25 --out ".\runs"
```

Run the ScienceDirect metadata import after the `9225` browser is logged in:

```powershell
python .\scripts\sciencedirect_drission_run.py --port 9225 --query "solid electrolyte interphase" --year-from 2021 --year-to 2026 --if-min 5 --limit 25 --out ".\runs\sei"
```

## Output

A run directory contains files like:

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

`已入库Zotero文献清单.csv` is the main success log. `待处理文献清单.csv` records items that could not be imported or needed manual attention.

## Impact Factors

ScienceDirect search results usually do not include impact factors. Paper Harbor will not invent them.

If you want reliable impact-factor filtering, add a trusted CSV at:

```text
内部数据_一般不用打开/journal_impact_factors.csv
```

Recommended columns:

```csv
journal,issn,eissn,impact_factor,year,source,notes
```

## Privacy And Safety

This repository does not include accounts, cookies, Zotero databases, PDFs, CSV run outputs, browser profiles, or institution credentials. Runtime outputs such as `runs/`, `内部数据_一般不用打开/`, `.sqlite`, `.pdf`, and `.csv` files are ignored by default.

Users log in themselves. Paper Harbor does not enter passwords, solve CAPTCHAs, bypass access controls, or fetch papers from unofficial sources.
