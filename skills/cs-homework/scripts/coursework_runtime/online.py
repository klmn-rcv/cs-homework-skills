"""Optional historical material checks; native Agent tools read online content."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .context import fingerprint


def valid_url(url):
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Online materials need an HTTP(S) URL without embedded credentials")
    return url


def load_receipt(path):
    path = Path(path).resolve()
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != 1 or receipt.get("kind") != "online-material-receipt":
        raise ValueError("Unrecognized online material receipt")
    valid_url(receipt["url"])
    if receipt.get("method") not in {"http", "tool"} or receipt.get("access_status") not in {"fetched", "partial", "unavailable"}:
        raise ValueError("Invalid online access receipt")
    if receipt["method"] == "tool" and (not isinstance(receipt.get("tool"), str) or not receipt["tool"].strip()
                                        or not isinstance(receipt.get("tool_receipt"), str) or not receipt["tool_receipt"].strip()):
        raise ValueError("Tool captures must retain their actual tool provenance")
    files = {"receipt.json": path.read_bytes()}
    for prefix in ["body", "text"]:
        name = receipt.get(prefix + "_path")
        if name is None and prefix == "text":
            continue
        if name != {"body": "body.bin", "text": "content.txt"}[prefix]:
            raise ValueError("Receipt cache paths must name body.bin and content.txt")
        material = path.parent / name
        if fingerprint(material) != receipt.get(prefix + "_sha256"):
            raise ValueError(f"Online cache hash mismatch: {material}")
        files[name] = material.read_bytes()
    if len(files["body.bin"]) != receipt.get("size_bytes"):
        raise ValueError("Online cache size mismatch")
    return receipt, files


def prepare_online_source(workspace, source):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", source["id"]):
        raise ValueError("Online source IDs must use 1-64 letters, digits, dots, underscores or hyphens")
    valid_url(source.get("url", ""))
    if not isinstance(source.get("purpose"), str) or not source["purpose"].strip():
        raise ValueError("Online sources need a material purpose")
    reading = source.get("reading", {})
    if reading.get("status") not in {"read", "partial", "unread"} or not isinstance(reading.get("note"), str) or not reading["note"].strip():
        raise ValueError("Online sources need actual reading coverage or an access gap")
    if not source.get("receipt"):
        if not isinstance(reading.get("read_at"), str) or not reading["read_at"].strip():
            raise ValueError("Reading notes need the actual read/attempt time")
        source["access_status"] = "unavailable" if reading["status"] == "unread" else "observed"
        source["retrieved_at"] = reading["read_at"]
        return
    path = Path(source.get("receipt", ""))
    path = path if path.is_absolute() else workspace / path
    receipt, _ = load_receipt(path)
    if receipt["url"] != source["url"]:
        raise ValueError("Online source URL does not match its access receipt")
    reading = source.get("reading", {})
    if reading.get("status") not in {"read", "partial", "unread"} or not isinstance(reading.get("note"), str) or not reading["note"].strip():
        raise ValueError("Online sources need reading status and a concrete note about coverage or gaps")
    if reading["status"] != "unread":
        if receipt["access_status"] == "unavailable" or not receipt.get("text_sha256"):
            raise ValueError("Unavailable or unextracted contents must remain unread")
        if reading.get("content_sha256") != receipt["text_sha256"]:
            raise ValueError("Reading must identify the cached text version actually read")
        if reading["status"] == "read" and receipt["access_status"] == "partial":
            raise ValueError("An incomplete capture cannot be marked fully read")
    source.update({"receipt": str(path.resolve()), "sha256": receipt["body_sha256"],
                   "access_status": receipt["access_status"], "retrieved_at": receipt["retrieved_at"]})


def archive_online_sources(workspace, sources):
    pending = {}
    for source in sources:
        if source["kind"] != "online" or not source.get("receipt"):
            continue
        path = Path(source["receipt"])
        path = path if path.is_absolute() else workspace / path
        _, files = load_receipt(path)
        digest = hashlib.sha256(files["receipt.json"]).hexdigest()
        directory = Path(".coursework/materials") / source["id"] / digest
        source["receipt"] = (directory / "receipt.json").as_posix()
        for name, data in files.items():
            target = directory / name
            existing = workspace / target
            if existing.is_file():
                if existing.read_bytes() != data:
                    raise ValueError(f"Immutable online capture was modified: {target}")
            else:
                pending[target.as_posix()] = data
    return pending


def online_check(workspace, source, *, refresh=False):
    """Inspect saved evidence only; remote reading belongs to native Agent tools.

    refresh is retained for old Python callers, but never performs a request.
    A historical snapshot check and current remote freshness are different facts.
    """
    reading = source.get("reading", {})
    status = reading.get("status", "unread")
    item = {"source_id": source["id"], "reading_status": status,
            "status": "recorded" if status in {"read", "partial"} else "unread",
            "freshness": "not_revisited", "last_read_at": reading.get("read_at", source.get("retrieved_at")),
            "coverage": reading.get("note", "No reading coverage recorded")}
    if not isinstance(reading.get("note"), str) or not reading["note"].strip() or not item["last_read_at"]:
        item.update({"status": "unread", "reason": "Historical reading coverage/time is missing; inspect actual notes before using requirements"})
    if source.get("receipt"):
        try:
            receipt, _ = load_receipt(Path(workspace) / source["receipt"])
            item.update({"cache_status": "verified", "access_status": receipt["access_status"]})
        except (OSError, ValueError, KeyError) as exc:
            item.update({"status": "cache_invalid", "cache_status": "damaged", "error": str(exc)})
    else:
        item["cache_status"] = "not_saved"
    return item
