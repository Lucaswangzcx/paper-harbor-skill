#!/usr/bin/env python3
"""CNKI runner using DrissionPage CDP takeover.

Metadata-only workflow: search CNKI in the logged-in browser, save screened
candidate tables, then save Zotero metadata items one by one. Never downloads
full text.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

from DrissionPage import Chromium, ChromiumOptions

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from zotero_bridge import locate_zotero_data_dir, save_metadata_item


CANDIDATE_HEADERS = [
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
    "zotero_status",
    "zotero_item_key",
    "next_action",
    "notes",
]

MAX_SCAN_RECORDS = 50
MAX_RESULT_PAGES = 5


def write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def assert_cdp_port_ready(port: int) -> None:
    try:
        with urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3) as response:
            response.read(256)
    except Exception as exc:
        raise RuntimeError(
            f"未检测到已登录浏览器调试端口 {port}。请先运行 open_lit_browser.ps1 -Site cnki 并在浏览器里登录知网。"
        ) from exc


def connect_browser(port: int):
    assert_cdp_port_ready(port)
    opts = ChromiumOptions()
    opts.set_local_port(port)
    try:
        return Chromium(opts)
    except TypeError:
        return Chromium(addr_or_opts=opts)


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


def search_url(query: str) -> str:
    return (
        "https://kns.cnki.net/kns8s/defaultresult/index"
        "?crossids=YSTT4HG0%2CLSTPFY1C%2CJUP3MUPD%2CMPMFIG1A%2CWQ0UVIAA%2CBLZOG7CK%2CPWFIRAGL%2CEMRPGLPA%2CNLBO1Z6R%2CNN3FJMUV"
        "&korder=SU&kw="
        + quote(query)
    )


def perform_search(tab, query: str) -> None:
    """Open the stable CNKI KNS result page for this query.

    CNKI may route the home-page search box to scholar.cnki.net/home for
    English queries. That page is a different "foreign database" portal and its
    DOM is not the KNS result list that EasyScholar and this runner expect.
    """
    tab.get(search_url(query))
    tab.wait.doc_loaded()
    time.sleep(2.5)
    current_url = str(getattr(tab, "url", "") or "").lower()
    if "scholar.cnki.net/home" in current_url or "www.cnki.net" in current_url:
        tab.get(search_url(query))
        tab.wait.doc_loaded()
        time.sleep(2.5)


def js_collect_results() -> str:
    return r"""
const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
const rows = [...document.querySelectorAll('table.result-table-list tr')]
  .filter((tr) => tr.querySelector('a.fz14[href*="/kcms2/article/abstract"]'));
const items = [];
for (const tr of rows) {
  const cells = [...tr.querySelectorAll('td')].map((td) => clean(td.innerText || td.textContent));
  const titleAnchor = tr.querySelector('a.fz14[href*="/kcms2/article/abstract"]');
  const title = clean(titleAnchor ? titleAnchor.innerText || titleAnchor.textContent : '');
  if (!title) continue;
  const authorAnchors = [...tr.querySelectorAll('a.KnowledgeNetLink')];
  const authors = authorAnchors.map((a) => clean(a.innerText || a.textContent)).filter(Boolean).join('; ');
  const journalAnchors = [...tr.querySelectorAll('a[href*="navi.cnki.net/knavi"]')];
  const journal = journalAnchors.length ? clean(journalAnchors[journalAnchors.length - 1].innerText || journalAnchors[journalAnchors.length - 1].textContent) : '';
  const text = clean(tr.innerText || tr.textContent);
  const dateMatch = text.match(/\b(20\d{2}|19\d{2})(?:-\d{1,2})?(?:-\d{1,2})?/);
  const year = dateMatch ? dateMatch[1] : '';
  const doiMatch = text.match(/10\.\d{4,9}\/[-._;()/:A-Z0-9]+/i);
  const ifMatch = text.match(/\bIF\s*([0-9]+(?:\.[0-9]+)?)/i);
  const htmlRead = /HTML阅读|原版阅读|CNKI AI阅读/.test(text);
  items.push({
    title,
    authors,
    journal,
    publication_year: year,
    impact_factor: ifMatch ? ifMatch[1] : '',
    metric_year: ifMatch ? '' : '',
    metric_source: ifMatch ? 'EasyScholar visible badge on CNKI result page' : '',
    doi: doiMatch ? doiMatch[0] : '',
    url: titleAnchor.href.split('#')[0],
    access_status: htmlRead ? 'official CNKI reading link visible' : 'metadata visible in CNKI result',
    notes: ifMatch
      ? 'CNKI result page metadata; IF read from visible EasyScholar badge'
      : 'CNKI result page metadata; IF待核验：结果页未显示 EasyScholar IF，需用户刷新插件或手动核验'
  });
}
return items;
"""


def js_click_next_page() -> str:
    return r"""
const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
const controls = [...document.querySelectorAll('a, button, span')];
const next = controls.find((el) => {
  const text = clean(el.innerText || el.textContent || el.getAttribute('title') || el.getAttribute('aria-label'));
  const cls = `${el.className || ''}`.toLowerCase();
  const disabled = el.disabled || /disabled|disable|unavailable/.test(cls) || el.getAttribute('aria-disabled') === 'true';
  if (disabled) return false;
  return /下一页|下页|next/i.test(text) || text === '>' || /next/.test(cls);
});
if (!next) return false;
next.click();
return true;
"""


def js_article_metadata() -> str:
    return r"""
const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
const body = clean(document.body ? document.body.innerText : '');
const title = clean(document.querySelector('h1, .wx-tit, .brief h1')?.innerText) || document.title.replace(/- 中国知网.*/, '');
const doi = (body.match(/10\.\d{4,9}\/[-._;()/:A-Z0-9]+/i) || [''])[0];
const year = (body.match(/\b(20\d{2}|19\d{2})\b/) || [''])[0];
const abstract =
  clean(document.querySelector('#ChDivSummary, .abstract-text, .abstract, [id*="abstract"]')?.innerText) ||
  (body.match(/摘要[:：]\s*(.{20,600}?)(关键词|Key words|分类号|DOI|$)/)?.[1] || '');
return { title, doi, publication_year: year, abstract: clean(abstract) };
"""


def prefer_cnki_title(search_title: str, page_title: str) -> tuple[str, str]:
    """Keep the search-result title unless the page title looks trustworthy."""
    search = (search_title or "").strip()
    page = (page_title or "").strip()
    if not page:
        return search, ""
    lowered = page.lower()
    suspicious_tokens = (
        "自动登录",
        "登录",
        "sign in",
        "log in",
        "cnki",
        "中国知网",
        "知网",
    )
    if any(token in lowered for token in suspicious_tokens):
        return search or page, page
    if search and len(page) < len(search) * 0.6:
        return search, page
    return page, ""


def parse_float(value: object) -> float | None:
    try:
        text = str(value or "").strip()
        return float(text) if text else None
    except ValueError:
        return None


def apply_filters(rows: list[dict[str, str]], year_from: str, year_to: str, if_min: str = "") -> list[dict[str, str]]:
    filtered = []
    min_if = parse_float(if_min)
    for row in rows:
        year_text = row.get("publication_year", "")
        year = int(year_text) if year_text.isdigit() else 0
        if year_from and year and year < int(year_from):
            continue
        if year_to and year and year > int(year_to):
            continue
        current_if = parse_float(row.get("impact_factor", ""))
        if min_if is not None:
            if current_if is None:
                row["priority"] = "中"
                row["next_action"] = "pending IF verification; EasyScholar IF badge not visible"
            elif current_if <= min_if:
                row["priority"] = "低"
                row["next_action"] = f"skip Zotero import; IF {current_if:g} does not exceed {min_if:g}"
            else:
                row["priority"] = "高"
                row["next_action"] = "save metadata to Zotero; no full-text download"
        else:
            row["priority"] = "高" if current_if is not None else "中"
            row["next_action"] = "save metadata to Zotero; no full-text download"
        row["source"] = "CNKI"
        row["impact_factor"] = row.get("impact_factor", "")
        row["metric_year"] = row.get("metric_year", "")
        row["metric_source"] = row.get("metric_source", "")
        row["zotero_status"] = "not_attempted"
        row["zotero_item_key"] = ""
        filtered.append(row)
    return filtered


def save_candidate_tables(run_dir: Path, rows: list[dict[str, str]]) -> None:
    candidate_rows = [
        [
            row.get("priority", "中"),
            row.get("title", ""),
            row.get("authors", ""),
            row.get("journal", ""),
            row.get("publication_year", ""),
            row.get("impact_factor", ""),
            row.get("metric_year", ""),
            row.get("metric_source", ""),
            row.get("doi", ""),
            "CNKI",
            row.get("url", ""),
            row.get("abstract", ""),
            row.get("access_status", ""),
            row.get("zotero_status", "not_attempted"),
            row.get("zotero_item_key", ""),
            row.get("next_action", ""),
            row.get("notes", ""),
        ]
        for row in rows
    ]
    write_csv(run_dir / "候选文献总表.csv", CANDIDATE_HEADERS, candidate_rows)
    write_csv(
        run_dir / "文章地址总表.csv",
        ["record_id", "source", "title", "url", "doi", "publication_year", "journal", "discovered_at", "status"],
        [
            [
                f"cnki-{idx + 1:03d}",
                "CNKI",
                row.get("title", ""),
                row.get("url", ""),
                row.get("doi", ""),
                row.get("publication_year", ""),
                row.get("journal", ""),
                datetime.now().isoformat(timespec="seconds"),
                "candidate_saved",
            ]
            for idx, row in enumerate(rows)
        ],
    )
    write_csv(run_dir / "高优先级文献.csv", CANDIDATE_HEADERS, [r for r in candidate_rows if r[0] == "高"])
    write_csv(run_dir / "中优先级文献.csv", CANDIDATE_HEADERS, [r for r in candidate_rows if r[0] == "中"])
    write_csv(run_dir / "低优先级文献.csv", CANDIDATE_HEADERS, [r for r in candidate_rows if r[0] == "低"])


def run(args: argparse.Namespace) -> dict[str, object]:
    run_dir = Path(args.out).resolve()
    internal_dir = run_dir / "内部数据_一般不用打开"
    (internal_dir / "logs").mkdir(parents=True, exist_ok=True)
    (internal_dir / "raw_exports").mkdir(parents=True, exist_ok=True)

    browser = connect_browser(args.port)
    tab = open_tab(browser)
    tab.set.timeouts(12)
    perform_search(tab, args.query)

    target_count = max(int(args.limit), 0)
    scan_cap = min(MAX_SCAN_RECORDS, max(target_count * 5, target_count, 20))
    raw_results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    stopped_reason = ""

    def add_page_results(page_rows: list[dict[str, str]]) -> None:
        for row in page_rows:
            key = row.get("url") or row.get("title", "")
            if not key or key in seen_urls:
                continue
            seen_urls.add(key)
            raw_results.append(row)

    for page_index in range(MAX_RESULT_PAGES):
        page_rows = []
        for _ in range(12):
            time.sleep(2)
            page_rows = tab.run_js(js_collect_results()) or []
            if page_rows:
                break
            text = tab.run_js('return (document.body && document.body.innerText || "").slice(0, 2000)') or ""
            if re.search(r"验证码|安全验证|异常|captcha|robot|verify", text, re.I):
                stopped_reason = "site verification or unusual activity detected"
                break
        add_page_results(page_rows)
        screened_so_far = apply_filters(raw_results, str(args.year_from or ""), str(args.year_to or ""), str(args.if_min or ""))
        importable_so_far = [row for row in screened_so_far if row.get("priority") == "高"]
        if len(importable_so_far) >= target_count or len(raw_results) >= scan_cap or stopped_reason:
            break
        clicked_next = bool(tab.run_js(js_click_next_page()))
        if not clicked_next:
            stopped_reason = "no more CNKI result pages found"
            break
        tab.wait.doc_loaded()
        time.sleep(2.5)

    if not raw_results and not stopped_reason:
        tab.get(search_url(args.query))
        tab.wait.doc_loaded()
        for _ in range(12):
            time.sleep(2)
            page_rows = tab.run_js(js_collect_results()) or []
            if page_rows:
                add_page_results(page_rows)
                break
            text = tab.run_js('return (document.body && document.body.innerText || "").slice(0, 2000)') or ""
            if re.search(r"验证码|安全验证|异常|captcha|robot|verify", text, re.I):
                stopped_reason = "site verification or unusual activity detected"
                break

    (internal_dir / "raw_exports" / "cnki_search_results.json").write_text(
        json.dumps(raw_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    results = apply_filters(raw_results, str(args.year_from or ""), str(args.year_to or ""), str(args.if_min or ""))
    save_candidate_tables(run_dir, results)

    zotero_rows: list[list[str]] = []
    pending_rows: list[list[str]] = []
    zotero_saved = 0
    attempts = 0
    data_dir = locate_zotero_data_dir(args.zotero_data_dir)
    importable_results = [row for row in results if row.get("priority") == "高"]
    non_importable_results = [row for row in results if row.get("priority") != "高"]
    for row in non_importable_results:
        reason = "IF missing or does not satisfy requested threshold"
        if row.get("priority") == "中":
            reason = "EasyScholar IF badge not visible; IF threshold cannot be verified"
        elif row.get("priority") == "低":
            reason = "Impact factor does not satisfy requested threshold"
        pending_rows.append([
            row.get("title", ""),
            row.get("doi", ""),
            "CNKI",
            row.get("url", ""),
            reason,
            row.get("next_action", "manual review required"),
            row.get("priority", "中"),
        ])

    max_attempts = min(int(args.max_attempts or target_count), target_count, len(importable_results))

    for row in importable_results[:max_attempts]:
        attempts += 1
        tab.get(row["url"])
        tab.wait.doc_loaded()
        time.sleep(1.5)
        page_text = tab.run_js('return (document.body && document.body.innerText || "").slice(0, 3000)') or ""
        if re.search(r"验证码|安全验证|异常访问|captcha|robot|verify", page_text, re.I):
            row["zotero_status"] = "pending"
            row["next_action"] = "site verification shown; user should resolve manually before rerun"
            pending_rows.append([row["title"], row.get("doi", ""), "CNKI", row["url"], "site verification detected", row["next_action"], row.get("priority", "中")])
            save_candidate_tables(run_dir, results)
            write_csv(run_dir / "已入库Zotero文献清单.csv", ["record_id", "title", "doi", "source", "url", "journal", "publication_year", "zotero_item_key", "zotero_status", "saved_at", "access_status", "notes"], zotero_rows)
            write_csv(run_dir / "待处理文献清单.csv", ["title", "doi", "source", "url", "reason", "next_action", "priority"], pending_rows)
            continue
        info = tab.run_js(js_article_metadata()) or {}
        title, generic_page_title = prefer_cnki_title(row.get("title", ""), str(info.get("title") or ""))
        row["title"] = title
        row["doi"] = info.get("doi") or row.get("doi", "")
        row["publication_year"] = info.get("publication_year") or row.get("publication_year", "")
        row["abstract"] = info.get("abstract") or row.get("abstract", "")
        if generic_page_title and generic_page_title != row["title"]:
            note = row.get("notes", "").strip()
            extra = f"CNKI article page showed generic title '{generic_page_title}'; kept search-result title."
            row["notes"] = f"{note}; {extra}" if note else extra
        result = save_metadata_item(row, data_dir=data_dir)
        if result.get("ok"):
            zotero_saved += 1
            row["zotero_status"] = str(result.get("status") or "saved")
            row["zotero_item_key"] = str(result.get("zotero_item_key") or "")
            row["next_action"] = "metadata stored in Zotero; no full-text download attempted"
            zotero_rows.append([
                f"cnki-{attempts:03d}",
                row["title"],
                row.get("doi", ""),
                "CNKI",
                row["url"],
                row.get("journal", ""),
                row.get("publication_year", ""),
                row.get("zotero_item_key", ""),
                row.get("zotero_status", ""),
                datetime.now().isoformat(timespec="seconds"),
                row.get("access_status", ""),
                "metadata only; full-text download intentionally disabled",
            ])
        else:
            row["zotero_status"] = "pending"
            row["next_action"] = "manual Zotero save or rerun after Zotero is available"
            pending_rows.append([row["title"], row.get("doi", ""), "CNKI", row["url"], str(result.get("reason", "Zotero metadata save failed")), row["next_action"], row.get("priority", "中")])

        save_candidate_tables(run_dir, results)
        write_csv(run_dir / "已入库Zotero文献清单.csv", ["record_id", "title", "doi", "source", "url", "journal", "publication_year", "zotero_item_key", "zotero_status", "saved_at", "access_status", "notes"], zotero_rows)
        write_csv(run_dir / "待处理文献清单.csv", ["title", "doi", "source", "url", "reason", "next_action", "priority"], pending_rows)

    save_candidate_tables(run_dir, results)
    write_csv(run_dir / "已入库Zotero文献清单.csv", ["record_id", "title", "doi", "source", "url", "journal", "publication_year", "zotero_item_key", "zotero_status", "saved_at", "access_status", "notes"], zotero_rows)
    write_csv(run_dir / "待处理文献清单.csv", ["title", "doi", "source", "url", "reason", "next_action", "priority"], pending_rows)

    html = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>文献整理报告</title><body>
<h1>文献整理报告</h1>
<p>运行方式：DrissionPage 接管 9226 已登录知网浏览器；模式：Zotero 元数据入库，不下载 PDF。</p>
<p>关键词：{args.query}</p>
<p>年份：{args.year_from}-{args.year_to}</p>
<p>目标合格入库数量：{target_count}</p>
<p>候选：{len(results)}，符合入库条件：{len(importable_results)}，尝试入库：{attempts}，成功/已存在：{zotero_saved}，待处理：{len(pending_rows)}</p>
<p>停止原因：{stopped_reason or '达到目标或完成本页检索'}</p>
<p>说明：候选清单先保存；本流程不会点击知网下载、HTML阅读、原版阅读或 CNKI AI 阅读按钮。</p>
</body></html>"""
    (run_dir / "文献整理报告.html").write_text(html, encoding="utf-8")
    summary = {
        "runner": "cnki_drission",
        "download_method": "metadata_only",
        "query": args.query,
        "year_from": args.year_from,
        "year_to": args.year_to,
        "target_qualified_records": target_count,
        "raw_results": len(raw_results),
        "candidates": len(results),
        "eligible_for_zotero": len(importable_results),
        "attempted": attempts,
        "downloaded": 0,
        "zotero_saved": zotero_saved,
        "pending": len(pending_rows),
        "stopped_reason": stopped_reason or "target reached or result pages exhausted",
    }
    (internal_dir / "logs" / "cnki_drission_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9226)
    parser.add_argument("--query")
    parser.add_argument("--query-file")
    parser.add_argument("--year-from", default="")
    parser.add_argument("--year-to", default="")
    parser.add_argument("--if-min", default="")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--max-attempts", type=int, default=0)
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
