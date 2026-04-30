#!/usr/bin/env python3
"""Check whether the expected browser debugging port is reachable."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


SITES = {
    "wos": {
        "port": 9224,
        "name": "Web of Science",
        "url": "https://www.webofscience.com/wos/woscc/basic-search",
    },
    "sciencedirect": {
        "port": 9225,
        "name": "ScienceDirect",
        "url": "https://www.sciencedirect.com/search",
    },
    "cnki": {
        "port": 9226,
        "name": "中国知网/CNKI",
        "url": "https://www.cnki.net/",
    },
}

ALIASES = {
    "webofscience": "wos",
    "web-of-science": "wos",
    "web_of_science": "wos",
    "science-direct": "sciencedirect",
    "science_direct": "sciencedirect",
    "elsevier": "sciencedirect",
    "知网": "cnki",
    "中国知网": "cnki",
}


def normalize_site(value: str) -> str:
    key = value.strip().lower().replace(" ", "")
    key = ALIASES.get(key, key)
    if key not in SITES:
        raise SystemExit(f"Unsupported site: {value}. Choose one of: {', '.join(SITES)}")
    return key


def fetch_json(url: str, timeout: float = 2.0) -> object:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True, help="wos, sciencedirect, or cnki")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    site_key = normalize_site(args.site)
    site = SITES[site_key]
    port = site["port"]
    base = f"http://127.0.0.1:{port}"

    result = {
        "site": site_key,
        "name": site["name"],
        "port": port,
        "expected_url": site["url"],
        "reachable": False,
        "browser": None,
        "tabs": [],
        "error": None,
    }

    try:
        version = fetch_json(f"{base}/json/version")
        tabs = fetch_json(f"{base}/json/list")
        result["reachable"] = True
        result["browser"] = version
        result["tabs"] = [
            {
                "title": tab.get("title", ""),
                "url": tab.get("url", ""),
                "type": tab.get("type", ""),
            }
            for tab in tabs
            if isinstance(tab, dict)
        ]
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["reachable"]:
        print(f"OK: {site['name']} browser debugging port {port} is reachable.")
        if result["tabs"]:
            print("Open tabs:")
            for tab in result["tabs"][:8]:
                print(f"- {tab['title']} | {tab['url']}")
    else:
        print(f"NOT READY: {site['name']} port {port} is not reachable.")
        print("Open Chrome with this command and log in:")
        print(
            'Start-Process chrome.exe -ArgumentList @('
            f'"--remote-debugging-port={port}",'
            f'"--user-data-dir=$env:LOCALAPPDATA\\CodexLitProfiles\\{site_key}",'
            f'"{site["url"]}")'
        )
        if result["error"]:
            print(f"Check error: {result['error']}")

    return 0 if result["reachable"] else 2


if __name__ == "__main__":
    sys.exit(main())
