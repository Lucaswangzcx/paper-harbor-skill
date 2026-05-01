#!/usr/bin/env python3
"""Zotero bridge for paper-harbor.

This script talks to Zotero Desktop through Zotero's local connector endpoint.
It can save metadata-only journal items and can still read/copy attachments
that Zotero Connector has already saved legally from the user's browser session.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def safe_file_part(value: str, fallback: str = "zotero_attachment") -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return (text or fallback)[:120]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_text(value: str) -> str:
    return re.sub(r"\W+", "", value or "", flags=re.UNICODE).lower()


def normalize_doi(value: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text, flags=re.I)
    return text.lower()


def ping_zotero(timeout: float = 3.0) -> dict[str, str | bool]:
    try:
        with urlopen("http://127.0.0.1:23119/connector/ping", timeout=timeout) as response:
            content = response.read(512).decode("utf-8", errors="replace")
            return {
                "ok": True,
                "content": content,
                "version": response.headers.get("X-Zotero-Version", ""),
                "api_version": response.headers.get("X-Zotero-Connector-API-Version", ""),
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def connector_post(method: str, payload: dict[str, object], timeout: float = 15.0) -> dict[str, object]:
    ping = ping_zotero()
    if not ping.get("ok"):
        return {"ok": False, "reason": f"Zotero connector is not reachable: {ping.get('error', 'unknown error')}"}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        f"http://127.0.0.1:23119/connector/{method}",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Zotero-Version": str(ping.get("version") or "9.0.1"),
            "X-Zotero-Connector-API-Version": str(ping.get("api_version") or "3"),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            if "application/json" in (response.headers.get("Content-Type") or ""):
                data = json.loads(raw) if raw else {}
            else:
                data = {"content": raw}
            return {"ok": True, "status_code": response.status, "data": data}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}


def candidate_data_dirs(explicit: str | None = None) -> list[Path]:
    roots: list[Path] = []
    if explicit:
        roots.append(Path(explicit).expanduser())
    env_dir = os.environ.get("ZOTERO_DATA_DIR")
    if env_dir:
        roots.append(Path(env_dir).expanduser())
    home = Path.home()
    roots.append(home / "Zotero")
    appdata = os.environ.get("APPDATA")
    if appdata:
        profile_root = Path(appdata) / "Zotero" / "Zotero" / "Profiles"
        if profile_root.exists():
            for profile in profile_root.iterdir():
                roots.append(profile / "zotero")
                roots.append(profile)
    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            resolved = str(root.resolve())
        except Exception:
            resolved = str(root)
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(root)
    return deduped


def locate_zotero_data_dir(explicit: str | None = None) -> Path | None:
    for root in candidate_data_dirs(explicit):
        if (root / "zotero.sqlite").exists():
            return root
    return None


def existing_item_key(data_dir: Path, *, title: str, doi: str, url: str = "") -> str:
    db_path = data_dir / "zotero.sqlite"
    wanted_doi = normalize_doi(doi)
    wanted_title = normalize_text(title)
    wanted_url = (url or "").strip().lower()
    query = """
    SELECT
      items.key,
      items.dateAdded,
      (
        SELECT idv.value
        FROM itemData id
        JOIN fields f ON f.fieldID = id.fieldID
        JOIN itemDataValues idv ON idv.valueID = id.valueID
        WHERE id.itemID = items.itemID AND f.fieldName = 'title'
        LIMIT 1
      ) AS title,
      (
        SELECT idv.value
        FROM itemData id
        JOIN fields f ON f.fieldID = id.fieldID
        JOIN itemDataValues idv ON idv.valueID = id.valueID
        WHERE id.itemID = items.itemID AND f.fieldName = 'DOI'
        LIMIT 1
      ) AS doi,
      (
        SELECT idv.value
        FROM itemData id
        JOIN fields f ON f.fieldID = id.fieldID
        JOIN itemDataValues idv ON idv.valueID = id.valueID
        WHERE id.itemID = items.itemID AND f.fieldName = 'url'
        LIMIT 1
      ) AS url
    FROM items
    WHERE items.itemID NOT IN (SELECT itemID FROM itemAttachments)
      AND items.itemID NOT IN (SELECT itemID FROM deletedItems)
    ORDER BY items.dateAdded DESC
    LIMIT 1000
    """
    with sqlite_connection(db_path) as conn:
        for key, _added, current_title, current_doi, current_url in conn.execute(query):
            if wanted_doi and normalize_doi(current_doi or "") == wanted_doi:
                return str(key or "")
            if wanted_url and str(current_url or "").strip().lower() == wanted_url:
                return str(key or "")
            current = normalize_text(current_title or "")
            if wanted_title and current and (wanted_title in current or current in wanted_title):
                return str(key or "")
    return ""


def zotero_item_from_metadata(row: dict[str, str]) -> dict[str, object]:
    title = row.get("title", "").strip()
    item: dict[str, object] = {
        "itemType": "journalArticle",
        "title": title,
        "creators": [],
        "publicationTitle": row.get("journal", "").strip(),
        "date": row.get("publication_year", "").strip(),
        "DOI": normalize_doi(row.get("doi", "")),
        "url": row.get("url", "").strip(),
        "abstractNote": row.get("abstract", "").strip(),
        "language": "",
        "tags": [{"tag": "paper-harbor"}],
        "notes": [
            {
                "note": (
                    "Imported by paper-harbor as metadata only. "
                    f"Source: {row.get('source', 'ScienceDirect')}; "
                    f"Access signal: {row.get('access_status', '')}; "
                    f"Priority: {row.get('priority', '')}; "
                    f"Notes: {row.get('notes', '')}"
                )
            }
        ],
        "attachments": [],
    }
    return {key: value for key, value in item.items() if value not in ("", [], None)}


def save_metadata_item(row: dict[str, str], data_dir: Path | None = None) -> dict[str, object]:
    data_dir = data_dir or locate_zotero_data_dir()
    if not data_dir:
        return {"ok": False, "status": "pending", "reason": "Zotero data directory not found"}
    title = row.get("title", "").strip()
    if not title:
        return {"ok": False, "status": "pending", "reason": "missing title"}
    existing = existing_item_key(data_dir, title=title, doi=row.get("doi", ""), url=row.get("url", ""))
    if existing:
        return {"ok": True, "status": "already_exists", "zotero_item_key": existing}
    item = zotero_item_from_metadata(row)
    session = f"paper-harbor-{int(time.time() * 1000)}"
    payload = {
        "sessionID": session,
        "uri": row.get("url", "") or "https://www.sciencedirect.com/",
        "proxy": None,
        "items": [item],
    }
    result = connector_post("saveItems", payload)
    if not result.get("ok"):
        return {"ok": False, "status": "pending", "reason": result.get("reason", "saveItems failed")}
    key = ""
    data = result.get("data")
    if isinstance(data, dict):
        items = data.get("items") or data.get("data") or []
        if isinstance(items, list) and items and isinstance(items[0], dict):
            key = str(items[0].get("key") or "")
    deadline = time.time() + 8
    while not key and time.time() < deadline:
        time.sleep(1)
        key = existing_item_key(data_dir, title=title, doi=row.get("doi", ""), url=row.get("url", ""))
    return {
        "ok": True,
        "status": "saved",
        "zotero_item_key": key,
        "connector_response": data,
    }


@dataclass
class ZoteroAttachment:
    title: str
    doi: str
    item_key: str
    attachment_key: str
    attachment_path: Path
    date_added: str
    date_modified: str
    content_type: str


def sqlite_connection(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
    return sqlite3.connect(uri, uri=True)


def zotero_datetime_to_epoch(value: str) -> float:
    if not value:
        return 0.0
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            pass
    return 0.0


def recent_attachments(data_dir: Path, since_epoch: float = 0.0) -> list[ZoteroAttachment]:
    db_path = data_dir / "zotero.sqlite"
    storage_dir = data_dir / "storage"
    query = """
    SELECT
      parent.itemID,
      parent.key,
      parent.dateAdded,
      parent.dateModified,
      (
        SELECT idv.value
        FROM itemData id
        JOIN fields f ON f.fieldID = id.fieldID
        JOIN itemDataValues idv ON idv.valueID = id.valueID
        WHERE id.itemID = parent.itemID AND f.fieldName = 'title'
        LIMIT 1
      ) AS title,
      (
        SELECT idv.value
        FROM itemData id
        JOIN fields f ON f.fieldID = id.fieldID
        JOIN itemDataValues idv ON idv.valueID = id.valueID
        WHERE id.itemID = parent.itemID AND f.fieldName = 'DOI'
        LIMIT 1
      ) AS doi,
      child.key AS attachmentKey,
      child.dateAdded AS attachmentDateAdded,
      child.dateModified AS attachmentDateModified,
      ia.path,
      ia.contentType
    FROM items parent
    JOIN itemAttachments ia ON ia.parentItemID = parent.itemID
    JOIN items child ON child.itemID = ia.itemID
    WHERE ia.path IS NOT NULL
    ORDER BY child.dateAdded DESC, parent.dateAdded DESC
    LIMIT 250
    """
    rows: list[ZoteroAttachment] = []
    with sqlite_connection(db_path) as conn:
        for row in conn.execute(query):
            (
                _item_id,
                item_key,
                parent_added,
                parent_modified,
                title,
                doi,
                attachment_key,
                attachment_added,
                attachment_modified,
                raw_path,
                content_type,
            ) = row
            added = attachment_added or parent_added or ""
            modified = attachment_modified or parent_modified or ""
            if since_epoch and max(zotero_datetime_to_epoch(added), zotero_datetime_to_epoch(modified)) < since_epoch:
                continue
            if not raw_path:
                continue
            if str(raw_path).startswith("storage:"):
                rel = str(raw_path).split(":", 1)[1]
                file_path = storage_dir / str(attachment_key) / rel
            else:
                file_path = Path(str(raw_path))
                if not file_path.is_absolute():
                    file_path = storage_dir / str(attachment_key) / file_path
            if file_path.suffix.lower() != ".pdf" and "pdf" not in str(content_type or "").lower():
                continue
            if not file_path.exists():
                continue
            rows.append(
                ZoteroAttachment(
                    title=title or "",
                    doi=doi or "",
                    item_key=item_key or "",
                    attachment_key=attachment_key or "",
                    attachment_path=file_path,
                    date_added=added,
                    date_modified=modified,
                    content_type=content_type or "",
                )
            )
    return rows


def match_attachment(attachments: list[ZoteroAttachment], *, title: str, doi: str) -> ZoteroAttachment | None:
    wanted_doi = normalize_doi(doi)
    wanted_title = normalize_text(title)
    for attachment in attachments:
        if wanted_doi and normalize_doi(attachment.doi) == wanted_doi:
            return attachment
    for attachment in attachments:
        current = normalize_text(attachment.title)
        if wanted_title and (wanted_title in current or current in wanted_title):
            return attachment
    return attachments[0] if len(attachments) == 1 else None


def copy_attachment(attachment: ZoteroAttachment, out_dir: Path, title: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{safe_file_part(title or attachment.title, attachment.attachment_path.stem)}.pdf"
    counter = 2
    while target.exists():
        target = out_dir / f"{safe_file_part(title or attachment.title, attachment.attachment_path.stem)} ({counter}).pdf"
        counter += 1
    shutil.copy2(attachment.attachment_path, target)
    return target


def wait_for_attachment(
    *,
    data_dir: Path,
    title: str,
    doi: str,
    out_dir: Path,
    since_epoch: float,
    timeout: float,
) -> dict[str, object]:
    start = time.time()
    last_count = 0
    while time.time() - start < timeout:
        attachments = recent_attachments(data_dir, since_epoch=since_epoch)
        last_count = len(attachments)
        match = match_attachment(attachments, title=title, doi=doi)
        if match:
            copied = copy_attachment(match, out_dir, title)
            return {
                "ok": True,
                "filename": copied.name,
                "path": str(copied),
                "sha256": sha256(copied),
                "zotero_item_key": match.item_key,
                "zotero_attachment_key": match.attachment_key,
                "zotero_title": match.title,
                "zotero_doi": match.doi,
            }
        time.sleep(2)
    return {"ok": False, "reason": f"timeout waiting for Zotero PDF attachment; recent_attachment_count={last_count}"}


def cmd_doctor(args: argparse.Namespace) -> int:
    ping = ping_zotero()
    data_dir = locate_zotero_data_dir(args.data_dir)
    result = {
        "zotero_connector_reachable": ping,
        "zotero_data_dir": str(data_dir) if data_dir else "",
        "zotero_sqlite": str(data_dir / "zotero.sqlite") if data_dir else "",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ping.get("ok") and data_dir else 1


def cmd_wait(args: argparse.Namespace) -> int:
    data_dir = locate_zotero_data_dir(args.data_dir)
    if not data_dir:
        print(json.dumps({"ok": False, "reason": "Zotero data directory not found"}, ensure_ascii=False, indent=2))
        return 2
    result = wait_for_attachment(
        data_dir=data_dir,
        title=args.title or "",
        doi=args.doi or "",
        out_dir=Path(args.out).resolve(),
        since_epoch=float(args.since_epoch or 0),
        timeout=float(args.timeout),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", help="Zotero data directory containing zotero.sqlite")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor")
    doctor.set_defaults(func=cmd_doctor)

    wait = sub.add_parser("wait")
    wait.add_argument("--title", default="")
    wait.add_argument("--doi", default="")
    wait.add_argument("--out", required=True)
    wait.add_argument("--since-epoch", type=float, default=0)
    wait.add_argument("--timeout", type=float, default=120)
    wait.set_defaults(func=cmd_wait)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
