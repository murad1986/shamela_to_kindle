from __future__ import annotations

import hashlib
import json
import os
from typing import Optional, Tuple


def _base_dir() -> str:
    base = os.environ.get("SHAMELA_CACHE_DIR")
    if not base:
        base = os.path.join(os.getcwd(), ".cache", "shamela_books")
    os.makedirs(base, exist_ok=True)
    return base


def _key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def _paths(kind: str, url: str) -> tuple[str, str]:
    k = _key(url)
    d = os.path.join(_base_dir(), kind, k[:2])
    os.makedirs(d, exist_ok=True)
    data_path = os.path.join(d, f"{k}.bin")
    meta_path = os.path.join(d, f"{k}.json")
    return data_path, meta_path


def get_bytes(kind: str, url: str) -> Optional[Tuple[bytes, Optional[str]]]:
    data_path, meta_path = _paths(kind, url)
    if not os.path.exists(data_path):
        return None
    try:
        with open(data_path, "rb") as fh:
            data = fh.read()
        ctype = None
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as mf:
                meta = json.load(mf)
                ctype = meta.get("content_type")
        return data, ctype
    except OSError:
        return None


def put_bytes(kind: str, url: str, data: bytes, content_type: Optional[str] = None) -> None:
    data_path, meta_path = _paths(kind, url)
    try:
        with open(data_path, "wb") as fh:
            fh.write(data)
        meta = {"content_type": content_type} if content_type else {}
        if meta:
            with open(meta_path, "w", encoding="utf-8") as mf:
                json.dump(meta, mf)
    except OSError:
        # Best-effort cache; ignore write errors
        return

