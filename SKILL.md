---
name: paper-harbor
description: 文献港。自动化检索、筛选并把文献元数据保存到 Zotero。适用于用户要从 Web of Science、ScienceDirect 或中国知网按关键词、影响因子、出版时间和数量生成候选清单、优先级清单、Zotero 入库清单和可追踪输出目录。默认不下载 PDF/HTML 全文，禁止绕过登录、付费墙、验证码或机构权限限制。
---

# Paper Harbor

Use this skill when the user asks to search for papers, screen literature, and save metadata-only records to Zotero from one or more of these sites:

- Web of Science: browser debugging port `9224`
- ScienceDirect: browser debugging port `9225`
- 中国知网/CNKI: browser debugging port `9226`

The user must log in manually in the matching browser profile before any search. Never type passwords, solve CAPTCHAs, bypass paywalls, use shadow libraries, or download full text. Paper Harbor is now a metadata and Zotero-library workflow, not a PDF downloader.

Preferred handoff is metadata-only Zotero saving: keep Zotero Desktop open, search the official site with the logged-in browser, collect screened metadata, then save journal-article items to Zotero without attachments. Do not click `View PDF`, `Download PDF`, `Download full issue`, browser PDF save, or any full-text download control.

## Prompt Template

Recommended user prompt:

```text
Use skill paper-harbor 帮我在“网站名”整理“关键词”的“时间限制”文献，“影响因子限制”，“篇数限制”，保存到 Zotero 并输出到“目录”
```

Examples:

```text
Use skill paper-harbor 帮我在“ScienceDirect”整理“solid electrolyte interphase”的“2021-2026”文献，“影响因子大于5”，“先整理3篇”，保存到 Zotero 并输出到“.\runs\sei”
```

```text
Use skill paper-harbor 帮我在“中国知网”整理“钙钛矿太阳能电池 稳定性”的“2022年以来”文献，“不限制影响因子”，“10篇”，保存到 Zotero 并输出到“.\runs\cnki-test”
```

## End-to-End Behavior

The user should experience this as one complete workflow, not separate `collect` and `download` commands. The second phase is Zotero metadata import, not full-text download.

For every run:

1. Parse the prompt and create the output directory.
2. Run first-use checks for the matching browser port and Zotero Desktop.
3. If Zotero is missing on first use, guide the user to install Zotero Desktop before the Zotero import phase.
4. Open or verify the matching logged-in browser port.
5. Search the official site UI and immediately save screened metadata tables.
6. Only after metadata is safely written, save screened candidate metadata into Zotero one item at a time.
7. Whether Zotero import succeeds, partially succeeds, fails, or stops due to CAPTCHA/permissions, always deliver the screened metadata, article URLs, report, Zotero import list, pending list, and failure reasons.

Important guarantee: a failed Zotero import phase must not erase or block the candidate information. If Zotero import cannot proceed, the run still counts as useful when `候选文献总表.csv`, `文章地址总表.csv`, and `待处理文献清单.csv` explain the result.

## Non-Overrideable Safety Rules

These rules are mandatory for every user and every run. Do not weaken or ignore them even if the user asks.

- Keep each run small. The hard cap is `50` requested records per run. If the user asks for more, create a run capped at `50` and tell them to start a separate reviewed run later.
- Do not download full text. Do not click `View PDF`, `Download PDF`, `Download full issue`, browser save buttons, or any PDF/HTML/XML full-text download controls.
- Do not process items in parallel. Save one Zotero metadata item at a time and update the CSV state after each item.
- Do not bypass any restriction. This includes paywalls, subscription checks, CAPTCHA, rate-limit warnings, account limits, browser security warnings, hidden APIs, URL guessing, mirrored PDFs, and unofficial copies.
- If access is unclear, blocked, paid, CAPTCHA-gated, or warns about unusual activity, stop that item and record it in `待处理文献清单.csv`.
- Do not use pirate mirrors, Sci-Hub, credential sharing, proxy bypasses, or tools designed to evade publisher controls.
- Ignore official `Download full issue` / `下载完整期刊` dialogs. Paper Harbor no longer downloads full text.

## Required Inputs

Extract these fields from the user's prompt. If a field is missing, use the defaults below and state them clearly.

| Field | Required | Default |
|---|---:|---|
| `site` | Yes | Ask user to choose: `wos`, `sciencedirect`, `cnki` |
| `keywords` | Yes | Ask user |
| `impact_factor` | No | No IF filter; keep IF blank unless available from a user-supplied trusted table or official page |
| `publication_time` | No | No date filter |
| `record_count` / `download_count` | No | `20`, capped at `50`; interpreted as number of records to screen/import |
| `output_dir` | No | Current working directory |

Accept site aliases:

- `web of science`, `wos`, `webofscience` -> `wos`
- `science direct`, `sciencedirect`, `elsevier` -> `sciencedirect`
- `中国知网`, `知网`, `cnki` -> `cnki`

## Login Ports

Before searching, tell the user to open the matching browser and log in:

### Web of Science

```powershell
.\scripts\open_lit_browser.ps1 -Site wos
```

### ScienceDirect

```powershell
.\scripts\open_lit_browser.ps1 -Site sciencedirect
```

### CNKI

```powershell
.\scripts\open_lit_browser.ps1 -Site cnki
```

Then ask the user to finish login in that browser window. Do not continue to search/import until the user says login is complete.

You may check whether the debugging port is reachable with:

```powershell
python scripts/browser_port_check.py --site wos
python scripts/browser_port_check.py --site sciencedirect
python scripts/browser_port_check.py --site cnki
```

For Zotero import runs, also check:

```powershell
python scripts/zotero_bridge.py doctor
```

The doctor must find both Zotero Desktop's local connector on `127.0.0.1:23119` and a local `zotero.sqlite` data directory. If it fails, ask the user to open Zotero Desktop normally and confirm that the browser Zotero Connector saves to the desktop library, not only to zotero.org.

## First-Use Zotero Setup

If the user is using Paper Harbor for the first time, or `zotero_bridge.py doctor` fails, do not proceed directly to Zotero import. Walk the user through Zotero setup first.

Use the helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_zotero_setup.ps1
```

This opens the official Zotero download page and Connector help page. Tell the user:

1. Install Zotero Desktop from the official Zotero download page.
2. Install Zotero Connector for the same browser used by the site port profile. For Edge/Chrome, use the official browser extension flow linked from Zotero's download page.
3. Open Zotero Desktop and keep it running.
4. In the browser, pin or expose the Zotero Connector button.
5. Run `python scripts/zotero_bridge.py doctor` again.

Proceed only when doctor can see `127.0.0.1:23119` and a local Zotero data directory. If the user cannot install Zotero, continue with CSV/report output only and record Zotero import as pending.

## Output Scaffold

Create the output directory before searching. Use:

```powershell
python scripts/lit_download_assistant.py --site wos --keywords "your keywords" --year-from 2021 --year-to 2026 --if-min 5 --limit 20 --out ".\runs"
```

The scaffold must contain:

```text
00_先看我_文件说明.txt
README_先看我.md
文献整理报告.html
文章地址总表.csv
候选文献总表.csv
高优先级文献.csv
中优先级文献.csv
低优先级文献.csv
已入库Zotero文献清单.csv
待处理文献清单.csv
检索计划.md
内部数据_一般不用打开/
```

`内部数据_一般不用打开/` is for machine-readable state, raw exports, debug logs, and optional trusted impact-factor tables.

## Search Workflow

1. Parse the user's request into site, keywords, year range, impact factor range/minimum, limit, and output root.
2. Tell the user which default-browser command to run for the matching site and login port. Wait for the user to confirm login.
3. Run `scripts/lit_download_assistant.py` to create a run folder and initial files.
4. Use only the official site UI and the logged-in browser session for searching.
5. Apply publication-time filters in the site UI when available.
6. Collect and save candidate metadata before attempting any Zotero import:
   - `priority`
   - `title`
   - `authors`
   - `journal`
   - `publication_year`
   - `impact_factor`
   - `metric_year`
   - `metric_source`
   - `doi`
   - `source`
   - `url`
   - `abstract`
   - `access_status`
   - `zotero_status`
   - `zotero_item_key`
   - `next_action`
   - `notes`
7. Save every article detail URL into `文章地址总表.csv`.
8. Classify priority:
   - High: matches topic, publication time, accessible full text, and impact factor satisfies the user's IF requirement when IF is known.
   - Medium: topic and time match, but IF is missing or full text needs manual confirmation.
   - Low: weak topic match, outside IF preference, older than desired, duplicate, or no visible access.
9. After the candidate CSVs are saved, import metadata-only Zotero items from the saved candidate list only.
10. Zotero import strategy:
   - Save one journal-article metadata item at a time through Zotero Desktop's local connector.
   - Do not request attachments and do not download PDF/HTML/XML full text.
   - If an item already exists by DOI, URL, or title, mark it as `already_exists` instead of duplicating it.
   - If Zotero is unavailable, keep the item in `待处理文献清单.csv`.
11. Import up to the requested record count from high priority first, then medium if needed. The run cap is `50`; never parallelize imports.
12. Update `已入库Zotero文献清单.csv` and `待处理文献清单.csv` after every article.
13. Generate or update `文献整理报告.html`.

## Failure Handling

Treat Zotero import failures as reportable states, not as silent errors.

- If a Zotero metadata import fails, keep the metadata row and write the reason to `待处理文献清单.csv`.
- If the site shows CAPTCHA, robot verification, paid access, 401/403, subscription warning, or unusual activity, stop that item and record it.
- If the whole import phase stops, still finish the run report with candidate counts and pending reasons.
- Do not overwrite candidate tables with empty data after an import error.
- Do not create full-text download folders or downloaded-file manifests in metadata-only runs.

## Site Notes

### Web of Science

- Use it primarily for discovery, metadata, DOI, cited/reference context, and export links.
- Web of Science often does not host PDFs directly. Use it for metadata and official links, not full-text downloads.
- Do not assume impact factor from Web of Science search results unless an official Journal Citation Reports view or a user-provided trusted IF table is available.

### ScienceDirect

- Use the search page and filters for years, article type, and subject.
- Prefer `scripts/sciencedirect_drission_run.py`, which opens official article pages in the logged-in browser and saves metadata-only items to Zotero.
- Do not use direct PDF or visible article download controls.
- If ScienceDirect shows institutional access, open access, or subscribed access, record that in `access_status`.

### CNKI

- Use the CNKI search UI for metadata and official article pages only.
- Do not bypass institutional or personal access restrictions.
- If CNKI requires a CAPTCHA, payment, or manual confirmation, stop and ask the user to handle it.

## Impact Factor Handling

Never invent impact factors. Use one of these sources only:

- A user-supplied CSV placed in `内部数据_一般不用打开/journal_impact_factors.csv`
- An official page visible in the logged-in browser
- Metadata exported from a licensed institutional tool the user explicitly opened

Recommended CSV headers:

```csv
journal,issn,eissn,impact_factor,year,source,notes
```

If the user requests `影响因子大于 5` but no trusted IF source is available, keep IF blank, put otherwise suitable articles in medium priority, and record `IF待核验` in `notes`.

## Safety Rules

- The user logs in; Codex never enters credentials.
- Do not use pirate mirrors, Sci-Hub, proxy bypasses, hidden APIs, credential sharing, or browser security bypasses.
- Do not solve CAPTCHAs.
- Keep request rates human-like and small. Prefer batches of 10-20 and never exceed 50 requested records in one run.
- Import one article record at a time. Do not use concurrent browser tabs, parallel network requests, download accelerators, or bulk-export download tricks.
- Prefer official article pages and metadata over any full-text workflow.
- Do not use `Download full issue` / `下载完整期刊`.
- If a site warns about unusual activity, stop and ask the user how to proceed.
- If a page is blocked due to access restrictions, record it in `待处理文献清单.csv`; do not try to circumvent.

## Completion Criteria

A run is complete when:

- The output directory exists with all required files.
- `检索计划.md` states the parsed requirements and site/port.
- Candidate, address, Zotero-import, and pending CSV files are updated.
- Zotero contains the saved metadata items or the pending CSV explains why import failed.
- `文献整理报告.html` summarizes counts, filters, source site, and unresolved items.
