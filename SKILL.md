---
name: paper-harbor
description: 文献港。自动化整理并下载用户有合法访问权限的文献全文。适用于用户要从 Web of Science、ScienceDirect 或中国知网按关键词、影响因子、出版时间和下载数量生成候选清单、优先级清单、下载 PDF/HTML、报告和可追踪输出目录。禁止绕过登录、付费墙、验证码或机构权限限制。
---

# Paper Harbor

Use this skill when the user asks to search for papers and download literature from one or more of these sites:

- Web of Science: browser debugging port `9224`
- ScienceDirect: browser debugging port `9225`
- 中国知网/CNKI: browser debugging port `9226`

The user must log in manually in the matching browser profile before any search or download. Never type passwords, solve CAPTCHAs, bypass paywalls, use shadow libraries, or download content that the user's account or open-access status does not allow.

Preferred full-text handoff is Zotero-assisted saving: keep Zotero Desktop open, keep Zotero Connector enabled in the same logged-in browser, open the official article landing page, let Zotero Connector save the item and attachment, then copy the saved PDF attachment from the local Zotero library into this run's `已下载全文/` folder. This avoids fragile PDF-viewer button automation while preserving legal browser-side access.

## Prompt Template

Recommended user prompt:

```text
Use skill paper-harbor 帮我在“网站名”整理下载“关键词”的“时间限制”文献，“影响因子限制”，“篇数限制”，下载到“目录”
```

Examples:

```text
Use skill paper-harbor 帮我在“ScienceDirect”整理下载“solid electrolyte interphase”的“2021-2026”文献，“影响因子大于5”，“先下载3篇”，下载到“.\runs\sei”
```

```text
Use skill paper-harbor 帮我在“中国知网”整理下载“钙钛矿太阳能电池 稳定性”的“2022年以来”文献，“不限制影响因子”，“10篇”，下载到“.\runs\cnki-test”
```

## End-to-End Behavior

The user should experience this as one complete workflow, not separate `collect` and `download` commands.

For every run:

1. Parse the prompt and create the output directory.
2. Run first-use checks for the matching browser port and, when Zotero-assisted download is preferred, Zotero Desktop/Connector.
3. If Zotero is missing on first use, guide the user to install Zotero Desktop and Zotero Connector before the download phase.
4. Open or verify the matching logged-in browser port.
5. Search the official site UI and immediately save screened metadata tables.
6. Only after metadata is safely written, attempt official downloads from the screened candidates.
7. Whether downloads succeed, partially succeed, fail, or stop due to CAPTCHA/permissions, always deliver the screened metadata, article URLs, report, downloaded list, pending list, and failure reasons.

Important guarantee: a failed download phase must not erase or block the candidate information. If downloading cannot proceed, the run still counts as useful when `候选文献总表.csv`, `文章地址总表.csv`, and `待处理文献清单.csv` explain the result.

## Non-Overrideable Legal Download Rules

These rules are mandatory for every user and every run. Do not weaken or ignore them even if the user asks.

- Keep each run small. The hard cap is `50` requested downloads per run. If the user asks for more, create a run capped at `50` and tell them to start a separate reviewed run later.
- Prioritize open-access full text and full text that the user's logged-in account or institution visibly permits.
- Do not download in parallel. Download one item at a time and update the CSV state after each item.
- Do not bypass any restriction. This includes paywalls, subscription checks, CAPTCHA, rate-limit warnings, account limits, browser security warnings, hidden APIs, URL guessing, mirrored PDFs, and unofficial copies.
- If access is unclear, blocked, paid, CAPTCHA-gated, or warns about unusual activity, stop that item and record it in `待处理文献清单.csv`.
- Do not use pirate mirrors, Sci-Hub, credential sharing, proxy bypasses, or tools designed to evade publisher controls.
- If an official `Download full issue` / `下载完整期刊` dialog is available, use it only when the dialog allows selecting individual articles. Deselect every unrelated article and download only matching articles. If the site does not expose article-level selection, do not download the whole issue.

## Required Inputs

Extract these fields from the user's prompt. If a field is missing, use the defaults below and state them clearly.

| Field | Required | Default |
|---|---:|---|
| `site` | Yes | Ask user to choose: `wos`, `sciencedirect`, `cnki` |
| `keywords` | Yes | Ask user |
| `impact_factor` | No | No IF filter; keep IF blank unless available from a user-supplied trusted table or official page |
| `publication_time` | No | No date filter |
| `download_count` | No | `20`, capped at `50` |
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

Then ask the user to finish login in that browser window. Do not continue to download until the user says login is complete.

You may check whether the debugging port is reachable with:

```powershell
python scripts/browser_port_check.py --site wos
python scripts/browser_port_check.py --site sciencedirect
python scripts/browser_port_check.py --site cnki
```

For Zotero-assisted runs, also check:

```powershell
python scripts/zotero_bridge.py doctor
```

The doctor must find both Zotero Desktop's local connector on `127.0.0.1:23119` and a local `zotero.sqlite` data directory. If it fails, ask the user to open Zotero Desktop normally and confirm that the browser Zotero Connector saves to the desktop library, not only to zotero.org.

## First-Use Zotero Setup

If the user is using Paper Harbor for the first time, or `zotero_bridge.py doctor` fails, do not proceed directly to download attempts. Walk the user through Zotero setup first.

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

Proceed only when doctor can see `127.0.0.1:23119` and a local Zotero data directory. If the user cannot install Zotero, continue with `--download-method direct`, but warn that ScienceDirect PDF saving may be less reliable.

## Output Scaffold

Create the output directory before searching. Use:

```powershell
python scripts/lit_download_assistant.py --site wos --keywords "your keywords" --year-from 2021 --year-to 2026 --if-min 5 --limit 20 --out ".\runs"
```

The scaffold must contain:

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
已下载全文/
内部数据_一般不用打开/
```

`内部数据_一般不用打开/` is for machine-readable state, raw exports, debug logs, and optional trusted impact-factor tables.

## Search Workflow

1. Parse the user's request into site, keywords, year range, impact factor range/minimum, limit, and output root.
2. Tell the user which default-browser command to run for the matching site and login port. Wait for the user to confirm login.
3. Run `scripts/lit_download_assistant.py` to create a run folder and initial files.
4. Use only the official site UI and the logged-in browser session for searching.
5. Apply publication-time filters in the site UI when available.
6. Collect and save candidate metadata before attempting any download:
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
   - `download_status`
   - `next_action`
   - `notes`
7. Save every article detail URL into `文章地址总表.csv`.
8. Classify priority:
   - High: matches topic, publication time, accessible full text, and impact factor satisfies the user's IF requirement when IF is known.
   - Medium: topic and time match, but IF is missing or full text needs manual confirmation.
   - Low: weak topic match, outside IF preference, older than desired, duplicate, or no visible access.
9. After the candidate CSVs are saved, attempt downloads from the saved candidate list only.
10. Preferred download strategy:
   - First choice for ScienceDirect, CNKI, and other publisher pages is Zotero-assisted saving from the official article landing page.
   - Keep the article page active, tell the user to click the Zotero Connector button when prompted, wait for Zotero to save the item/PDF attachment, then copy the attachment into `已下载全文/` and update CSVs.
   - If Zotero Connector saves only metadata or a snapshot, record the item as pending with the reason `Zotero did not save a PDF attachment`.
   - First, if the official page offers `Download full issue` / `下载完整期刊`, open that official dialog.
   - In the dialog, keep only the candidate article(s) that match the saved title/DOI/PII and deselect all other articles.
   - Download only the selected matching article(s).
   - If article-level deselection is unavailable or ambiguous, close the dialog and do not download the whole issue.
   - Fall back to the official single-article PDF link only when Zotero is unavailable or the user asks for direct mode.
11. Download up to `download_count` full texts from high priority first, then medium if needed. The run cap is `50`; never parallelize downloads.
12. Update `已下载文献清单.csv` and `待处理文献清单.csv` after every article.
13. Generate or update `下载报告.html`; keep `下载报告.pdf` as a summary PDF or a pointer to the HTML report if PDF rendering is unavailable.

## Failure Handling

Treat download failures as reportable states, not as silent errors.

- If a PDF/issue download fails, keep the metadata row and write the reason to `待处理文献清单.csv`.
- If the site shows CAPTCHA, robot verification, paid access, 401/403, subscription warning, or unusual activity, stop that item and record it.
- If the whole download phase stops, still finish the run report with candidate counts and pending reasons.
- Do not overwrite candidate tables with empty data after a download error.
- Do not mark a file as downloaded unless a real PDF/HTML/XML/ZIP file was saved and logged.

## Site Notes

### Web of Science

- Use it primarily for discovery, metadata, DOI, cited/reference context, and export links.
- Web of Science often does not host PDFs directly. Use official full-text links only when they route to accessible publisher pages.
- Do not assume impact factor from Web of Science search results unless an official Journal Citation Reports view or a user-provided trusted IF table is available.

### ScienceDirect

- Use the search page and filters for years, article type, and subject.
- Prefer `scripts/sciencedirect_drission_run.py --download-method zotero`, which opens official article pages in the logged-in browser and waits for Zotero Connector to save the item/PDF.
- Use direct PDF or visible article download controls only as a fallback.
- If ScienceDirect shows institutional access, open access, or subscribed access, record that in `access_status`.

### CNKI

- Use the CNKI search UI and official download buttons only.
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
- Keep request rates human-like and small. Prefer batches of 10-20 and never exceed 50 requested downloads in one run.
- Download one article at a time. Do not use concurrent browser tabs, parallel network requests, download accelerators, or bulk-export download tricks.
- Prefer open-access and visibly institution-authorized full text before any other item.
- `Download full issue` / `下载完整期刊` is allowed only as an official selector workflow. It must not save unrelated articles; unrelated articles must be unchecked before downloading.
- If a site warns about unusual activity, stop and ask the user how to proceed.
- If downloading a PDF fails due to access restrictions, record it in `待处理文献清单.csv`; do not try to circumvent.

## Completion Criteria

A run is complete when:

- The output directory exists with all required files.
- `检索计划.md` states the parsed requirements and site/port.
- Candidate, address, downloaded, and pending CSV files are updated.
- Downloaded full texts are in `已下载全文/`.
- `下载报告.html` summarizes counts, filters, source site, and unresolved items.
