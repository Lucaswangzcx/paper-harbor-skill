#!/usr/bin/env python3
"""Create and maintain a metadata-only literature screening directory."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SITES = {
    "wos": {
        "name": "Web of Science",
        "port": 9224,
        "url": "https://www.webofscience.com/wos/woscc/basic-search",
        "profile": "wos",
    },
    "sciencedirect": {
        "name": "ScienceDirect",
        "port": 9225,
        "url": "https://www.sciencedirect.com/search",
        "profile": "sciencedirect",
    },
    "cnki": {
        "name": "中国知网/CNKI",
        "port": 9226,
        "url": "https://www.cnki.net/",
        "profile": "cnki",
    },
}

HARD_RECORD_LIMIT = 50

ALIASES = {
    "webofscience": "wos",
    "web-of-science": "wos",
    "web_of_science": "wos",
    "wos": "wos",
    "science-direct": "sciencedirect",
    "science_direct": "sciencedirect",
    "sciencedirect": "sciencedirect",
    "elsevier": "sciencedirect",
    "知网": "cnki",
    "中国知网": "cnki",
    "cnki": "cnki",
}

CSV_HEADERS = {
    "文章地址总表.csv": [
        "record_id",
        "source",
        "title",
        "url",
        "doi",
        "publication_year",
        "journal",
        "discovered_at",
        "status",
    ],
    "候选文献总表.csv": [
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
    ],
    "高优先级文献.csv": [
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
        "zotero_status",
        "zotero_item_key",
        "next_action",
        "notes",
    ],
    "中优先级文献.csv": [
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
        "zotero_status",
        "zotero_item_key",
        "next_action",
        "notes",
    ],
    "低优先级文献.csv": [
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
        "zotero_status",
        "zotero_item_key",
        "next_action",
        "notes",
    ],
    "已入库Zotero文献清单.csv": [
        "record_id",
        "title",
        "doi",
        "source",
        "url",
        "journal",
        "publication_year",
        "zotero_item_key",
        "zotero_status",
        "saved_at",
        "access_status",
        "notes",
    ],
    "待处理文献清单.csv": [
        "title",
        "doi",
        "source",
        "url",
        "reason",
        "next_action",
        "priority",
    ],
}


def normalize_site(value: str | None) -> str | None:
    if not value:
        return None
    key = value.strip().lower().replace(" ", "")
    return ALIASES.get(key)


def parse_prompt(prompt: str) -> dict[str, Any]:
    text = prompt.strip()
    compact = text.lower().replace(" ", "")
    result: dict[str, Any] = {}

    for alias, site in ALIASES.items():
        if alias.lower() in compact or alias in text:
            result["site"] = site
            break

    quoted = re.findall(r"[\"“](.+?)[\"”]", text)
    site_words = {
        "web of science",
        "webofscience",
        "wos",
        "science direct",
        "sciencedirect",
        "elsevier",
        "中国知网",
        "知网",
        "cnki",
    }
    if quoted:
        for item in quoted:
            normalized_item = item.strip().lower().replace(" ", "")
            if item.strip().lower() in site_words or normalized_item in site_words:
                continue
            if re.search(r"[\\/]:?|^[A-Za-z]:", item) or item.strip().startswith("."):
                continue
            if re.search(r"(?:19|20)\d{2}|以来|以后|至今|影响因子|篇", item):
                continue
            result["keywords"] = item.strip()
            break
    else:
        keyword_match = re.search(r"(?:关键词|关键字|关于|检索)\s*[:：]?\s*([^，,。；;\n]+)", text)
        if keyword_match:
            result["keywords"] = keyword_match.group(1).strip()

    limit_match = re.search(r"(?:下载|要|需要)?\s*(\d{1,4})\s*(?:篇|个|条)", text)
    if limit_match:
        result["limit"] = int(limit_match.group(1))

    range_match = re.search(r"((?:19|20)\d{2})\s*[-~—至到]\s*((?:19|20)\d{2})", text)
    if range_match:
        result["year_from"] = int(range_match.group(1))
        result["year_to"] = int(range_match.group(2))
    else:
        since_match = re.search(r"((?:19|20)\d{2})\s*(?:年)?\s*(?:以后|以来|之后|至今)", text)
        if since_match:
            result["year_from"] = int(since_match.group(1))
            result["year_to"] = dt.date.today().year

    if_range = re.search(r"(?:影响因子|impact\s*factor|if)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*[-~—至到]\s*(\d+(?:\.\d+)?)", text, re.I)
    if if_range:
        result["if_min"] = float(if_range.group(1))
        result["if_max"] = float(if_range.group(2))
    else:
        if_min = re.search(r"(?:影响因子|impact\s*factor|if)\s*(?:大于|高于|>=|＞|>)\s*(\d+(?:\.\d+)?)", text, re.I)
        if if_min:
            result["if_min"] = float(if_min.group(1))
        if_max = re.search(r"(?:影响因子|impact\s*factor|if)\s*(?:小于|低于|<=|＜|<)\s*(\d+(?:\.\d+)?)", text, re.I)
        if if_max:
            result["if_max"] = float(if_max.group(1))

    zotero_collection = re.search(r"保存到\s*Zotero\s*(?:的|目录|collection)?\s*[\"“]([^\"”]+)[\"”]", text, re.I)
    if zotero_collection:
        result["zotero_collection"] = zotero_collection.group(1).strip()

    out_match = re.search(r"(?:下载到|输出到)\s*[\"“]?([^\"”\n]+)[\"”]?", text)
    if not out_match:
        out_match = re.search(r"保存到(?!\s*Zotero)\s*[\"“]?([^\"”\n]+)[\"”]?", text, re.I)
    if out_match:
        result["out"] = out_match.group(1).strip().rstrip("。；;,，")

    return result


def slugify(value: str, max_len: int = 48) -> str:
    safe = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value, flags=re.UNICODE).strip("_")
    return (safe or "literature")[:max_len]


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def write_csv(path: Path, headers: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)


def minimal_pdf_bytes(title: str) -> bytes:
    text = f"{title} - see HTML report for Chinese details."
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 14 Tf 72 720 Td ({escaped}) Tj ET\n".encode("ascii", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("ascii")
        out += obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    return bytes(out)


def login_command(site_key: str) -> str:
    site = SITES[site_key]
    return f'.\\scripts\\open_lit_browser.ps1 -Site {site_key}'


def create_scaffold(args: argparse.Namespace) -> Path:
    prompt_text = args.prompt or ""
    if args.prompt_file:
        prompt_text = Path(args.prompt_file).expanduser().read_text(encoding="utf-8")
    prompt_values = parse_prompt(prompt_text)

    site_key = normalize_site(args.site) or prompt_values.get("site")
    if not site_key:
        raise SystemExit("Missing --site. Choose wos, sciencedirect, or cnki.")

    keywords = args.keywords or prompt_values.get("keywords")
    if not keywords:
        raise SystemExit("Missing --keywords, or provide a prompt containing keywords.")

    requested_limit = args.limit or prompt_values.get("limit") or 20
    limit = min(requested_limit, HARD_RECORD_LIMIT)
    limit_capped = requested_limit > HARD_RECORD_LIMIT
    year_from = args.year_from if args.year_from is not None else prompt_values.get("year_from")
    year_to = args.year_to if args.year_to is not None else prompt_values.get("year_to")
    if_min = args.if_min if args.if_min is not None else prompt_values.get("if_min")
    if_max = args.if_max if args.if_max is not None else prompt_values.get("if_max")

    site = SITES[site_key]
    default_collection = {
        "wos": "web of science",
        "sciencedirect": "science direct",
        "cnki": "中国知网",
    }.get(site_key, site["name"])
    zotero_collection = args.zotero_collection or prompt_values.get("zotero_collection") or default_collection
    out_root = Path(args.out or prompt_values.get("out") or ".").expanduser().resolve()
    run_name = args.run_name or f"{now_stamp()}_{site_key}_{slugify(keywords)}"
    run_dir = out_root / run_name
    internal = run_dir / "内部数据_一般不用打开"
    internal.mkdir(parents=True, exist_ok=True)
    (internal / "logs").mkdir(exist_ok=True)
    (internal / "raw_exports").mkdir(exist_ok=True)

    config = {
        "site": site_key,
        "site_name": site["name"],
        "port": site["port"],
        "start_url": site["url"],
        "keywords": keywords,
        "record_count": limit,
        "requested_record_count": requested_limit,
        "hard_record_limit": HARD_RECORD_LIMIT,
        "limit_capped": limit_capped,
        "year_from": year_from,
        "year_to": year_to,
        "impact_factor_min": if_min,
        "impact_factor_max": if_max,
        "zotero_collection": zotero_collection,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "login_command": login_command(site_key),
        "safety": {
            "scope": "Metadata-only literature screening and Zotero import. No full-text download.",
            "hard_rules": [
                f"Never exceed {HARD_RECORD_LIMIT} requested records in one run.",
                "Do not download PDF/HTML/XML full text.",
                "Do not process records in parallel; import one Zotero metadata item at a time.",
                "Do not bypass paywalls, CAPTCHA, subscription checks, rate limits, browser warnings, hidden APIs, mirrors, or unofficial copies.",
                "If access is unclear or blocked, record the item as pending instead of trying to circumvent.",
            ],
        },
    }

    write_text(internal / "config.json", json.dumps(config, ensure_ascii=False, indent=2))
    write_text(internal / "zotero_import_state.json", json.dumps({"imported": [], "pending": []}, ensure_ascii=False, indent=2))
    write_text(
        internal / "journal_impact_factors.csv",
        "journal,issn,eissn,impact_factor,year,source,notes\n",
    )

    for filename, headers in CSV_HEADERS.items():
        write_csv(run_dir / filename, headers)

    year_text = "不限" if year_from is None and year_to is None else f"{year_from or ''}-{year_to or ''}".strip("-")
    if_text = "不限"
    if if_min is not None and if_max is not None:
        if_text = f"{if_min}-{if_max}"
    elif if_min is not None:
        if_text = f">= {if_min}"
    elif if_max is not None:
        if_text = f"<= {if_max}"

    readme = f"""# 先看我

本目录是一次文献检索与 Zotero 入库任务的输出目录。

- 网站：{site["name"]}
- 浏览器调试端口：{site["port"]}
- 关键词：{keywords}
- 出版时间：{year_text}
- 影响因子要求：{if_text}
- 计划整理数量：{limit}{"（已按单次上限 50 自动限制）" if limit_capped else ""}
- Zotero 目录：{zotero_collection}

## 强制合规规则

- 单次运行最多整理 50 篇。
- 不下载 PDF，不点击全文下载按钮，不处理 PDF 预览页。
- 不并发处理，一次只保存一条 Zotero 元数据。
- 不绕过付费墙、验证码、权限限制、异常访问提醒或网站安全提示。
- 权限不清楚、需要付费、需要验证码、或访问失败的文献，仍保留候选信息并放入待处理清单。

## 先登录

请在 PowerShell 里打开对应默认浏览器，然后在弹出的浏览器窗口中手动登录站点，再登录 EasyScholar：

```powershell
{login_command(site_key)}
```

登录完成后，刷新结果页，确认 EasyScholar 的 IF 标签可见，再让 Codex 继续检索和 Zotero 入库。

## 首次运行准备

请确保已安装并启用：

1. Zotero Desktop
2. 当前浏览器里的 Zotero Connector
3. 当前浏览器里的 EasyScholar

并在 Zotero 里创建/选中 collection：`{zotero_collection}`。如果页面支持，EasyScholar 会在检索结果旁显示 IF，Paper Harbor 会读取这些可见标签；Web of Science、ScienceDirect 和知网都按同样的提醒和流程执行。

## 合规说明

这里只保存题名、DOI、期刊、年份、地址等元数据到 Zotero，不下载全文。遇到验证码、付费、权限不足或异常活动提醒时，应停止并由你手动处理。
"""
    write_text(run_dir / "README_先看我.md", readme)

    plain_readme = f"""请先阅读 README_先看我.md

网站：{site["name"]}
端口：{site["port"]}
关键词：{keywords}
出版时间：{year_text}
影响因子：{if_text}
计划整理数量：{limit}
Zotero 目录：{zotero_collection}

重要：用户必须自己登录；不得绕过付费墙、验证码或权限限制。
"""
    write_text(run_dir / "00_先看我_文件说明.txt", plain_readme)

    plan = f"""# 检索计划

## 任务参数

- 网站：{site["name"]} (`{site_key}`)
- 端口：`{site["port"]}`
- 起始网址：{site["url"]}
- 关键词：{keywords}
- 出版时间：{year_text}
- 影响因子：{if_text}
- 整理数量：{limit}{"（用户请求 " + str(requested_limit) + "，已按单次上限 50 自动限制）" if limit_capped else ""}
- Zotero 目录：{zotero_collection}

## 强制合规规则

1. 单次运行最多整理 50 篇。
2. 不下载 PDF，不点击全文下载按钮，不处理 PDF 预览页。
3. 不并发处理，一次只保存一条 Zotero 元数据并立即更新清单。
4. 不绕过付费墙、验证码、权限限制、异常访问提醒、隐藏接口、镜像站或非官方副本。
5. 权限不清楚、需要付费、需要验证码、或访问失败的文献，仍保留候选信息并写入 `待处理文献清单.csv`。

## 登录命令

```powershell
{login_command(site_key)}
```

## 执行步骤

1. 用户打开上述默认浏览器并完成站点登录。
2. 用户在同一个浏览器里登录 EasyScholar，并刷新结果页确认 IF 标签可见。
3. Codex 检查端口是否可访问。
4. Codex 检查 Zotero Desktop、Zotero Connector、EasyScholar 和 Zotero collection。
5. 在官方网站 UI 中检索关键词并套用出版时间筛选。
6. 收集候选文献、文章地址、DOI、期刊、年份、摘要、可访问状态。
7. 如果页面显示 EasyScholar IF 标签，读取并写入影响因子字段；如果没有显示，先停在候选层，提示用户登录 EasyScholar 并刷新页面后再重新运行。
8. 根据主题相关性、年份、可访问性和可信影响因子数据分为高/中/低优先级。
9. 先保存候选清单，再从候选清单串行写入 Zotero 的 `{zotero_collection}`。
10. 不打开下载完整期刊/Download full issue，不点击 View PDF 或 Download PDF。
11. 从高优先级开始保存 Zotero 元数据，直到达到数量要求或无更多匹配文献。
12. 更新 CSV 清单和文献整理报告。

## 影响因子规则

如需按影响因子筛选，请把可信来源整理到：

`内部数据_一般不用打开/journal_impact_factors.csv`

没有可信影响因子数据时，不臆造 IF；将匹配但 IF 待核验的文献放入中优先级。若用户明确要求 IF 阈值，未显示 IF 的条目不自动入库。
"""
    write_text(run_dir / "检索计划.md", plan)

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>文献整理报告</title>
  <style>
    body {{ font-family: Arial, "Microsoft YaHei", sans-serif; margin: 32px; line-height: 1.6; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 920px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f3f5f7; }}
    code {{ background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>文献整理报告</h1>
  <table>
    <tr><th>网站</th><td>{site["name"]}</td></tr>
    <tr><th>端口</th><td>{site["port"]}</td></tr>
    <tr><th>关键词</th><td>{keywords}</td></tr>
    <tr><th>出版时间</th><td>{year_text}</td></tr>
    <tr><th>影响因子</th><td>{if_text}</td></tr>
    <tr><th>计划整理数量</th><td>{limit}{"（已按单次上限 50 自动限制）" if limit_capped else ""}</td></tr>
    <tr><th>Zotero 目录</th><td>{zotero_collection}</td></tr>
    <tr><th>当前状态</th><td>目录已创建，等待登录、检索和 Zotero 入库。</td></tr>
  </table>
  <h2>强制合规规则</h2>
  <ul>
    <li>单次运行最多整理 50 篇。</li>
    <li>不下载 PDF，不点击全文下载按钮，不处理 PDF 预览页。</li>
    <li>不并发处理，一次只保存一条 Zotero 元数据。</li>
    <li>不绕过付费墙、验证码、权限限制、异常访问提醒或网站安全提示。</li>
    <li>权限不清楚或访问失败的文献写入待处理清单。</li>
  </ul>
  <h2>下一步</h2>
  <p>打开对应端口浏览器并登录，同时保持 Zotero Desktop 运行；随后继续执行检索，条目会写入 Zotero，并记录到 <code>已入库Zotero文献清单.csv</code>。</p>
</body>
</html>
"""
    write_text(run_dir / "文献整理报告.html", html)

    checksum = hashlib.sha256(json.dumps(config, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    write_text(internal / "run_checksum.sha256", checksum + "\n")
    write_text(
        internal / "mandatory_policy.json",
        json.dumps(
            {
                "hard_record_limit": HARD_RECORD_LIMIT,
                "serial_zotero_import_only": True,
                "metadata_only": True,
                "no_full_text_download": True,
                "no_bypass": True,
                "blocked_items_go_to_pending_csv": True,
                "zotero_collection": zotero_collection,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )

    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", help="Optional natural-language prompt to parse")
    parser.add_argument("--prompt-file", help="Read the natural-language prompt from a UTF-8 text file")
    parser.add_argument("--site", help="wos, sciencedirect, or cnki")
    parser.add_argument("--keywords", help="Literature keywords")
    parser.add_argument("--year-from", type=int, help="Start publication year")
    parser.add_argument("--year-to", type=int, help="End publication year")
    parser.add_argument("--if-min", type=float, help="Minimum impact factor")
    parser.add_argument("--if-max", type=float, help="Maximum impact factor")
    parser.add_argument("--limit", type=int, help="Record count to screen/import")
    parser.add_argument("--zotero-collection", help="Zotero collection name to save metadata into")
    parser.add_argument("--out", help="Output root directory")
    parser.add_argument("--run-name", help="Exact run folder name")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    run_dir = create_scaffold(args)
    print(f"Created literature metadata run directory:\n{run_dir}")
    print("\nNext step: open the default-browser command in README_先看我.md, log in to the site and EasyScholar, then continue the search.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
