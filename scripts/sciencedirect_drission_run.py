#!/usr/bin/env python3
"""ScienceDirect runner using DrissionPage CDP takeover."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from DrissionPage import Chromium, ChromiumOptions

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from zotero_bridge import locate_zotero_data_dir, ping_zotero, save_metadata_item, wait_for_attachment


def safe_file_part(value: str, fallback: str = "sciencedirect_article") -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return (text or fallback)[:120]


def write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def connect_browser(port: int):
    assert_cdp_port_ready(port)
    opts = ChromiumOptions()
    opts.set_local_port(port)
    try:
        return Chromium(opts)
    except TypeError:
        return Chromium(addr_or_opts=opts)


def assert_cdp_port_ready(port: int) -> None:
    url = f"http://127.0.0.1:{port}/json/version"
    try:
        with urlopen(url, timeout=3) as response:
            response.read(256)
    except Exception as exc:
        raise RuntimeError(
            f"未检测到已登录浏览器调试端口 {port}。请先运行 open_lit_browser.ps1 并在浏览器里登录 ScienceDirect。"
        ) from exc


def open_tab(browser, url: str | None = None):
    try:
        tab = browser.new_tab(url) if url else browser.new_tab()
    except Exception:
        tab = getattr(browser, "latest_tab", None)
        if isinstance(tab, str):
            tab = browser.get_tab(tab)
        if url and tab is not None:
            tab.get(url)
    if tab is None:
        raise RuntimeError("无法获取浏览器标签页。")
    try:
        tab.set.timeouts(12)
    except Exception:
        pass
    return tab


def search_url(query: str, year_from: str, year_to: str) -> str:
    params = {"qs": query}
    if year_from or year_to:
        params["date"] = f"{year_from or ''}-{year_to or ''}"
    return "https://www.sciencedirect.com/search?" + urlencode(params)


def js_collect_results() -> str:
    return r"""
const anchors = [...document.querySelectorAll('a[href*="/science/article/"]')];
const pdfLinks = anchors
  .map((a) => ({ href: new URL(a.getAttribute('href'), location.href).href, text: (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim() }))
  .filter((x) => /\/pdfft\?/i.test(x.href));
const piiFrom = (href) => {
  const match = href.match(/\/pii\/([^/?#]+)/i);
  return match ? match[1] : '';
};
const seen = new Set();
const items = [];
for (const a of anchors) {
  const href = new URL(a.getAttribute('href'), location.href).href.split('#')[0];
  const title = (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim();
  if (!title || title.length < 8 || title === 'View PDF' || /\/pdfft\?/i.test(href) || seen.has(href)) continue;
  seen.add(href);
  const pii = piiFrom(href);
  const matchingPdf = pdfLinks.find((x) => pii && piiFrom(x.href) === pii);
  const card = a.closest('li, article, div.ResultItem, div[class*="result"], div[class*="Result"], div[class*="card"]') || a.parentElement;
  const text = card ? (card.innerText || '').replace(/\s+/g, ' ').trim() : '';
  const afterTitle = text.includes(title) ? text.slice(text.indexOf(title) + title.length) : text;
  const dateMatch = afterTitle.match(/(?:Available online\s+)?(?:\d{1,2}\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}|\b20\d{2}\b/i);
  const journal = dateMatch ? afterTitle.slice(0, dateMatch.index).replace(/^(?:\s|,|;|-)+/, '').trim() : '';
  const yearMatch = text.match(/\b(20\d{2}|19\d{2})\b/);
  const doiMatch = text.match(/10\.\d{4,9}\/[-._;()/:A-Z0-9]+/i);
  const hasOpen = /open access/i.test(text);
  const hasFull = Boolean(matchingPdf) || /full text access|view pdf|open access/i.test(text);
  items.push({
    title,
    url: href,
    journal,
    publication_year: yearMatch ? yearMatch[1] : '',
    doi: doiMatch ? doiMatch[0] : '',
    pdf_url: matchingPdf ? matchingPdf.href : '',
    access_status: hasOpen ? 'open access visible in result' : (hasFull ? 'official View PDF visible in result' : 'unknown from result'),
    notes: (hasOpen ? 'Open access visible in result' : (hasFull ? 'Full text access/View PDF visible in result' : 'No visible full-text signal in result')) + '; IF待核验：ScienceDirect结果页不提供影响因子，需在 journal_impact_factors.csv 中补充可信IF'
  });
}
return items
  .sort((a, b) => {
    const score = (x) => (x.pdf_url ? 4 : 0) + (/open access/i.test(x.access_status) ? 2 : 0) + (/full text|view pdf/i.test(x.access_status) ? 1 : 0);
    return score(b) - score(a);
  })
  .slice(0, 30);
"""


def js_article_pdf_info() -> str:
    return r"""
const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
const title = clean(document.querySelector('h1')?.innerText) || document.title;
const text = clean(document.body ? document.body.innerText : '');
const doi = clean(document.querySelector('a[href*="doi.org"]')?.innerText || document.querySelector('a[href*="doi.org"]')?.href || '') || (text.match(/10\.\d{4,9}\/[-._;()/:A-Z0-9]+/i)?.[0] || '');
const controls = [...document.querySelectorAll('a, button, [role="button"]')].map((el) => ({
  text: clean(el.innerText || el.textContent || el.getAttribute('aria-label') || el.getAttribute('title') || ''),
  href: el.href || el.getAttribute('href') || '',
}));
const pdf = controls.find((x) => /view pdf|download pdf|pdf/i.test(x.text + ' ' + x.href) && /\/pdfft\?/i.test(x.href));
const fullIssue = controls.find((x) => /download\s+(full\s+)?issue|下载完整|整期下载|下载整期/i.test(x.text));
return { title, doi, pdf_url: pdf ? new URL(pdf.href, location.href).href : '', has_full_issue: Boolean(fullIssue), full_issue_text: fullIssue ? fullIssue.text : '' };
"""


def js_click_pdf_save() -> str:
    return r"""
const labels = ['download', 'save', '保存', '下载'];
const bad = ['print', 'zoom', 'rotate', 'fit', 'page', 'search', 'open'];
const seen = new Set();
const matches = [];
function visit(root) {
  if (!root || seen.has(root)) return;
  seen.add(root);
  let nodes = [];
  try { nodes = [...root.querySelectorAll('*')]; } catch (e) { return; }
  for (const el of nodes) {
    const text = [
      el.id,
      el.getAttribute && el.getAttribute('aria-label'),
      el.getAttribute && el.getAttribute('title'),
      el.getAttribute && el.getAttribute('alt'),
      el.innerText,
      el.textContent,
      el.className && String(el.className)
    ].filter(Boolean).join(' ').toLowerCase();
    if (labels.some(x => text.includes(x)) && !bad.some(x => text.includes(x))) {
      matches.push({ el, text });
    }
    if (el.shadowRoot) visit(el.shadowRoot);
  }
}
visit(document);
const ranked = matches.sort((a, b) => {
  const score = (x) =>
    (/\bdownload\b|下载/.test(x.text) ? 4 : 0) +
    (/\bsave\b|保存/.test(x.text) ? 3 : 0) +
    (/button|icon-button/.test(x.text) ? 1 : 0);
  return score(b) - score(a);
});
for (const item of ranked) {
  try {
    item.el.scrollIntoView && item.el.scrollIntoView({ block: 'center', inline: 'center' });
    item.el.click();
    return { clicked: true, text: item.text.slice(0, 180), candidates: ranked.length };
  } catch (e) {}
}
return { clicked: false, candidates: ranked.length };
"""


def save_candidate_tables(run_dir: Path, rows: list[dict[str, str]]) -> None:
    candidate_headers = [
        "priority",
        "title",
        "authors",
        "journal",
        "publication_year",
        "impact_factor",
        "metric_year",
        "metric_source",
        "doi",
        "source",
        "url",
        "abstract",
        "access_status",
        "download_status",
        "zotero_status",
        "zotero_item_key",
        "next_action",
        "notes",
    ]
    candidate_rows = [
        [
            row.get("priority", "中"),
            row.get("title", ""),
            "",
            row.get("journal", ""),
            row.get("publication_year", ""),
            "",
            "",
            "",
            row.get("doi", ""),
            "ScienceDirect",
            row.get("url", ""),
            "",
            row.get("access_status", ""),
            row.get("download_status", "not_attempted"),
            row.get("zotero_status", "not_attempted"),
            row.get("zotero_item_key", ""),
            row.get("next_action", "try official full issue selector or View PDF download"),
            row.get("notes", ""),
        ]
        for row in rows
    ]
    write_csv(run_dir / "候选文献总表.csv", candidate_headers, candidate_rows)
    write_csv(
        run_dir / "文章地址总表.csv",
        ["record_id", "source", "title", "url", "doi", "publication_year", "journal", "discovered_at", "status"],
        [
            [
                f"sd-{idx + 1:03d}",
                "ScienceDirect",
                row.get("title", ""),
                row.get("url", ""),
                row.get("doi", ""),
                row.get("publication_year", ""),
                row.get("journal", ""),
                datetime.now().isoformat(timespec="seconds"),
                row.get("access_status", ""),
            ]
            for idx, row in enumerate(rows)
        ],
    )
    priority_headers = [
        "title",
        "authors",
        "journal",
        "publication_year",
        "impact_factor",
        "metric_year",
        "metric_source",
        "doi",
        "source",
        "url",
        "access_status",
        "download_status",
        "zotero_status",
        "zotero_item_key",
        "next_action",
        "notes",
    ]
    for level, filename in [("高", "高优先级文献.csv"), ("中", "中优先级文献.csv"), ("低", "低优先级文献.csv")]:
        write_csv(
            run_dir / filename,
            priority_headers,
            [
                [
                    row.get("title", ""),
                    "",
                    row.get("journal", ""),
                    row.get("publication_year", ""),
                    "",
                    "",
                    "",
                    row.get("doi", ""),
                    "ScienceDirect",
                    row.get("url", ""),
                    row.get("access_status", ""),
                    row.get("download_status", "not_attempted"),
                    row.get("zotero_status", "not_attempted"),
                    row.get("zotero_item_key", ""),
                    row.get("next_action", "try official full issue selector or View PDF download"),
                    row.get("notes", ""),
                ]
                for row in rows
                if row.get("priority", "中") == level
            ],
        )


def wait_mission(mission, timeout: float = 90.0):
    start = time.time()
    while time.time() - start < timeout:
        for attr in ("is_done", "done", "success"):
            value = getattr(mission, attr, None)
            if value is True:
                return True
        state = str(getattr(mission, "state", "") or getattr(mission, "status", "")).lower()
        if any(token in state for token in ("done", "success", "completed", "finished")):
            return True
        if any(token in state for token in ("fail", "error", "cancel")):
            return False
        if hasattr(mission, "wait"):
            try:
                result = mission.wait(1)
                if result is not False and result is not None:
                    return True
            except TypeError:
                try:
                    result = mission.wait()
                    if result is not False and result is not None:
                        return True
                except Exception:
                    pass
            except Exception:
                pass
        time.sleep(1)
    return False


def newest_download(download_dir: Path, before: set[str]) -> Path | None:
    allowed = {".pdf", ".zip", ".html", ".xml"}
    files = [p for p in download_dir.iterdir() if p.is_file() and p.name not in before and p.suffix.lower() in allowed]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def wait_for_new_download(download_dir: Path, before: set[str], timeout: float = 90.0) -> Path | None:
    start = time.time()
    while time.time() - start < timeout:
        found = newest_download(download_dir, before)
        if found and found.exists() and found.stat().st_size > 1000:
            partials = list(download_dir.glob("*.crdownload")) + list(download_dir.glob("*.tmp"))
            if not partials:
                return found
        time.sleep(1)
    return None


def rename_downloaded_file(path: Path, title: str) -> Path:
    wanted = safe_file_part(title, path.stem)
    target = path.with_name(f"{wanted}{path.suffix.lower()}")
    if path.resolve() == target.resolve():
        return path
    counter = 2
    while target.exists():
        target = path.with_name(f"{wanted} ({counter}){path.suffix.lower()}")
        counter += 1
    path.replace(target)
    return target


def save_official_pdf_preview_url(pdf_url: str, download_dir: Path, title: str) -> Path | None:
    if not re.search(r"\.pdf(?:\?|$)|pdf\.sciencedirectassets\.com", pdf_url, re.I):
        return None
    target = download_dir / f"{safe_file_part(title)}.pdf"
    counter = 2
    while target.exists():
        target = download_dir / f"{safe_file_part(title)} ({counter}).pdf"
        counter += 1
    request = Request(
        pdf_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/pdf,*/*",
            "Referer": "https://www.sciencedirect.com/",
        },
    )
    with urlopen(request, timeout=60) as response:
        content_type = response.headers.get("content-type", "")
        data = response.read()
    if len(data) < 1000 or (b"%PDF" not in data[:1024] and "pdf" not in content_type.lower()):
        return None
    target.write_bytes(data)
    return target


def try_download_with_downloadkit(tab, pdf_url: str, download_dir: Path, title: str) -> tuple[Path | None, str]:
    before = {p.name for p in download_dir.iterdir() if p.is_file()}
    filename = safe_file_part(title)
    try:
        mission = tab.download.add(
            pdf_url,
            save_path=str(download_dir),
            rename=filename,
            suffix="pdf",
            file_exists="rename",
            split=False,
        )
        ok = wait_mission(mission, timeout=25)
        saved = wait_for_new_download(download_dir, before, timeout=5)
        if ok and saved:
            return rename_downloaded_file(saved, title), "Downloaded by DrissionPage DownloadKit from official View PDF link"
        return None, "DownloadKit did not produce a completed PDF"
    except Exception as exc:
        return None, f"DownloadKit failed: {exc}"


def try_download_with_pdf_viewer(browser, pdf_url: str, download_dir: Path, title: str) -> tuple[Path | None, str]:
    before = {p.name for p in download_dir.iterdir() if p.is_file()}
    pdf_tab = open_tab(browser, pdf_url)
    try:
        pdf_tab.set.download_path(str(download_dir))
        pdf_tab.set.when_download_file_exists("rename")
    except Exception:
        pass
    try:
        pdf_tab.wait.doc_loaded()
    except Exception:
        pass
    time.sleep(4)
    current_pdf_url = getattr(pdf_tab, "url", "") or ""
    try:
        saved = save_official_pdf_preview_url(current_pdf_url, download_dir, title)
        if saved:
            return saved, "Downloaded from the official PDF preview URL opened by the logged-in browser"
    except Exception as exc:
        preview_error = f"official PDF preview URL save failed: {exc}"
    else:
        preview_error = "official PDF preview URL was not a direct PDF response"
    try:
        result = pdf_tab.run_js(js_click_pdf_save()) or {}
    except Exception as exc:
        return None, f"{preview_error}; PDF viewer save button JS failed: {exc}"
    saved = wait_for_new_download(download_dir, before, timeout=90)
    if saved:
        clicked_text = str(result.get("text", "")).strip()
        note = "Downloaded by clicking the logged-in browser PDF viewer save button"
        if clicked_text:
            note += f"; control={clicked_text[:80]}"
        return rename_downloaded_file(saved, title), note
    if result.get("clicked"):
        return None, f"{preview_error}; PDF viewer save button was clicked but no completed file appeared in the output directory"
    return None, f"{preview_error}; PDF viewer save button was not found"


def try_download_with_zotero(tab, row: dict[str, str], info: dict[str, str], download_dir: Path, args: argparse.Namespace) -> tuple[Path | None, str]:
    data_dir = locate_zotero_data_dir(args.zotero_data_dir)
    if not data_dir:
        return None, "Zotero data directory not found; open Zotero once or pass --zotero-data-dir"
    ping = ping_zotero()
    if not ping.get("ok"):
        return None, "Zotero desktop connector port 23119 is not reachable; start Zotero Desktop and keep the browser Zotero Connector enabled"

    title = info.get("title") or row.get("title", "")
    doi = info.get("doi") or row.get("doi", "")
    started = time.time()
    # Keep the official article landing page active. The user/browser connector
    # saves from this page, which is where Zotero translators are most reliable.
    try:
        tab.set.activate()
    except Exception:
        pass
    print(
        f"[Zotero] 请在浏览器中点击 Zotero Connector 保存当前文章：{title[:90]}。"
        f"脚本将等待 {args.zotero_wait_seconds} 秒并自动复制 PDF 附件。",
        flush=True,
    )
    result = wait_for_attachment(
        data_dir=data_dir,
        title=title,
        doi=doi,
        out_dir=download_dir,
        since_epoch=started - 10,
        timeout=float(args.zotero_wait_seconds),
    )
    if result.get("ok"):
        return Path(str(result["path"])), (
            "Saved by Zotero Connector from the official article page; "
            f"copied from Zotero attachment {result.get('zotero_attachment_key', '')}"
        )
    return None, str(result.get("reason", "Zotero Connector did not produce a matching PDF attachment"))


def run(args: argparse.Namespace) -> dict[str, object]:
    run_dir = Path(args.out).resolve()
    download_dir = run_dir / "已下载全文"
    internal_dir = run_dir / "内部数据_一般不用打开"
    download_dir.mkdir(parents=True, exist_ok=True)
    (internal_dir / "logs").mkdir(parents=True, exist_ok=True)
    (internal_dir / "raw_exports").mkdir(parents=True, exist_ok=True)

    browser = connect_browser(args.port)
    tab = open_tab(browser)
    tab.set.download_path(str(download_dir))
    tab.set.when_download_file_exists("rename")
    tab.set.timeouts(12)

    url = search_url(args.query, str(args.year_from or ""), str(args.year_to or ""))
    tab.get(url)
    tab.wait.doc_loaded()
    results = []
    for _ in range(15):
        time.sleep(2)
        results = tab.run_js(js_collect_results()) or []
        if results:
            break
    (internal_dir / "raw_exports" / "sciencedirect_drission_search_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    for row in results:
        access = row.get("access_status", "")
        row["source"] = "ScienceDirect"
        row["priority"] = "中" if re.search(r"open access|view pdf|full text", access, re.I) else "低"
        row["download_status"] = "not_downloaded_by_design"
        row["zotero_status"] = "not_attempted"
        row["zotero_item_key"] = ""
        row["next_action"] = "save metadata to Zotero; no PDF download"
    save_candidate_tables(run_dir, results)

    zotero_rows: list[list[str]] = []
    pending_rows: list[list[str]] = []
    zotero_saved = 0
    attempts = 0
    data_dir = locate_zotero_data_dir(args.zotero_data_dir)
    max_requested = min(int(args.limit), len(results))
    max_attempts = min(int(args.max_attempts or max_requested), max_requested, len(results))

    for row in results[:max_attempts]:
        if zotero_saved >= args.limit:
            break
        attempts += 1
        tab.get(row["url"])
        tab.wait.doc_loaded()
        time.sleep(2)
        page_text = ""
        try:
            page_text = tab.run_js('return (document.body && document.body.innerText || "").slice(0, 2000)') or ""
        except Exception:
            page_text = ""
        if re.search(r"captcha|robot|verify|unusual activity|验证码|机器人|安全验证", page_text, re.I):
            row["zotero_status"] = "pending"
            row["next_action"] = "site verification shown; user should resolve manually before rerun"
            pending_rows.append([row["title"], row.get("doi", ""), "ScienceDirect", row["url"], "site verification or CAPTCHA detected", row["next_action"], row.get("priority", "中")])
            break
        info = tab.run_js(js_article_pdf_info()) or {}
        row["doi"] = info.get("doi") or row.get("doi", "")
        row["title"] = info.get("title") or row.get("title", "")
        row["has_full_issue"] = str(bool(info.get("has_full_issue")))
        result = save_metadata_item(row, data_dir=data_dir)
        if result.get("ok"):
            zotero_saved += 1
            row["zotero_status"] = str(result.get("status") or "saved")
            row["zotero_item_key"] = str(result.get("zotero_item_key") or "")
            row["next_action"] = "metadata stored in Zotero; no PDF download attempted"
            zotero_rows.append([
                f"sd-{attempts:03d}",
                row["title"],
                row.get("doi", ""),
                "ScienceDirect",
                row["url"],
                row.get("journal", ""),
                row.get("publication_year", ""),
                row.get("zotero_item_key", ""),
                row.get("zotero_status", ""),
                datetime.now().isoformat(timespec="seconds"),
                row.get("access_status", ""),
                "metadata only; PDF download intentionally disabled",
            ])
        else:
            row["zotero_status"] = "pending"
            row["next_action"] = "manual Zotero save or rerun after Zotero is available"
            pending_rows.append([row["title"], row.get("doi", ""), "ScienceDirect", row["url"], str(result.get("reason", "Zotero metadata save failed")), row["next_action"], row.get("priority", "中")])

        save_candidate_tables(run_dir, results)
        write_csv(run_dir / "已入库Zotero文献清单.csv", ["record_id", "title", "doi", "source", "url", "journal", "publication_year", "zotero_item_key", "zotero_status", "saved_at", "access_status", "notes"], zotero_rows)
        write_csv(run_dir / "已下载文献清单.csv", ["filename", "title", "doi", "source", "url", "downloaded_at", "license_or_access", "sha256", "notes"], [])
        write_csv(run_dir / "待处理文献清单.csv", ["title", "doi", "source", "url", "reason", "next_action", "priority"], pending_rows)

    save_candidate_tables(run_dir, results)
    write_csv(run_dir / "已入库Zotero文献清单.csv", ["record_id", "title", "doi", "source", "url", "journal", "publication_year", "zotero_item_key", "zotero_status", "saved_at", "access_status", "notes"], zotero_rows)
    write_csv(run_dir / "已下载文献清单.csv", ["filename", "title", "doi", "source", "url", "downloaded_at", "license_or_access", "sha256", "notes"], [])
    write_csv(run_dir / "待处理文献清单.csv", ["title", "doi", "source", "url", "reason", "next_action", "priority"], pending_rows)

    html = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>文献整理报告</title><body>
<h1>文献整理报告</h1>
<p>运行方式：DrissionPage 接管 9225 已登录浏览器；模式：Zotero 元数据入库，不下载 PDF。</p>
<p>关键词：{args.query}</p>
<p>年份：{args.year_from}-{args.year_to}</p>
<p>候选：{len(results)}，尝试入库：{attempts}，成功/已存在：{zotero_saved}，待处理：{len(pending_rows)}</p>
<p>说明：候选清单先保存；本流程不会下载全文或点击 PDF 下载按钮。Zotero 入库失败也会保留题名、地址、期刊、年份和失败原因。</p>
</body></html>"""
    (run_dir / "下载报告.html").write_text(html, encoding="utf-8")
    summary = {
        "runner": "drission",
        "download_method": "metadata_only",
        "query": args.query,
        "year_from": args.year_from,
        "year_to": args.year_to,
        "candidates": len(results),
        "attempted": attempts,
        "downloaded": 0,
        "zotero_saved": zotero_saved,
        "pending": len(pending_rows),
    }
    (internal_dir / "logs" / "sciencedirect_drission_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9225)
    parser.add_argument("--query")
    parser.add_argument("--query-file")
    parser.add_argument("--year-from", default="")
    parser.add_argument("--year-to", default="")
    parser.add_argument("--if-min", default="")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--max-attempts", type=int, default=0)
    parser.add_argument(
        "--download-method",
        choices=("metadata", "zotero-metadata", "auto", "direct", "zotero"),
        default="zotero-metadata",
        help="Deprecated compatibility option. The runner now saves metadata to Zotero and never downloads PDFs.",
    )
    parser.add_argument("--zotero-wait-seconds", type=int, default=90)
    parser.add_argument("--zotero-data-dir", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.query_file:
        args.query = Path(args.query_file).read_text(encoding="utf-8").strip()
    if not args.query:
        parser.error("--query or --query-file is required")
    return args


def main() -> int:
    summary = run(parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
