from __future__ import annotations

from typing import Optional, Tuple, List
import re
import contextlib
from urllib.parse import urlparse, quote_plus
from urllib.request import Request, urlopen

from .http import UA


def _maybe_convert_png_to_jpeg(data: bytes, mime: str) -> Tuple[bytes, str]:
    """If Pillow is available and mime is PNG, convert to JPEG for Kindle."""
    if mime != 'image/png':
        return data, mime
    try:
        from PIL import Image
        import io as _io

        im = Image.open(_io.BytesIO(data)).convert('RGB')
        out = _io.BytesIO()
        im.save(out, format='JPEG', quality=90)
        return out.getvalue(), 'image/jpeg'
    except Exception:
        return data, mime


def _parse_min_size(s: Optional[str]) -> Optional[Tuple[int, int]]:
    if not s:
        return None
    m = re.match(r"\s*(\d+)\s*[xX]\s*(\d+)\s*$", s)
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    if w <= 0 or h <= 0:
        return None
    return w, h


def _download_bytes(url: str) -> Optional[Tuple[bytes, str]]:
    try:
        req = Request(url, headers={"User-Agent": UA, "Referer": "https://www.google.com/"})
        with contextlib.closing(urlopen(req, timeout=30)) as resp:
            data = resp.read()
            ctype = resp.headers.get('Content-Type', '').split(';')[0].strip().lower()
            return data, ctype
    except Exception:
        return None


def _image_size(data: bytes) -> Optional[Tuple[int, int]]:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        if len(data) >= 33 and data[12:16] == b'IHDR':
            w = int.from_bytes(data[16:20], 'big')
            h = int.from_bytes(data[20:24], 'big')
            return w, h
        return None
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 1:
            if data[i] != 0xFF:
                i += 1
                continue
            while i < len(data) and data[i] == 0xFF:
                i += 1
            if i >= len(data):
                break
            marker = data[i]
            i += 1
            if marker in (0xD8, 0xD9):
                continue
            if i + 1 >= len(data):
                break
            seg_len = int.from_bytes(data[i : i + 2], 'big')
            if seg_len < 2 or i + seg_len > len(data):
                break
            if marker in (0xC0, 0xC2):
                if i + 7 < len(data):
                    h = int.from_bytes(data[i + 3 : i + 5], 'big')
                    w = int.from_bytes(data[i + 5 : i + 7], 'big')
                    return w, h
            i += seg_len
    return None


def _image_urls_from_google(query: str, max_n: int = 8) -> List[str]:
    url = f"https://www.google.com/search?tbm=isch&q={quote_plus(query)}"
    try:
        req = Request(url, headers={"User-Agent": UA, "Accept-Language": "ar,en;q=0.8"})
        with contextlib.closing(urlopen(req, timeout=20)) as resp:
            html_data = resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return []
    urls: List[str] = []
    for m in re.finditer(r'"ou":"(https?://[^\"]+)"', html_data):
        u = m.group(1)
        if 'gstatic.com' in u or 'google.' in urlparse(u).hostname or 'logo' in u:
            continue
        urls.append(u)
        if len(urls) >= max_n:
            break
    if not urls:
        for m in re.finditer(r'(https?://[^\"\s>]+\.(?:jpg|jpeg|png))', html_data, flags=re.I):
            u = m.group(1)
            if 'gstatic.com' in u or 'google.' in urlparse(u).hostname or 'logo' in u:
                continue
            urls.append(u)
            if len(urls) >= max_n:
                break
    return urls


def _image_urls_from_duckduckgo(query: str, max_n: int = 8) -> List[str]:
    url = f"https://duckduckgo.com/?q={quote_plus(query)}&iar=images&iax=images&ia=images"
    try:
        req = Request(url, headers={"User-Agent": UA, "Accept-Language": "ar,en;q=0.8"})
        with contextlib.closing(urlopen(req, timeout=20)) as resp:
            html_data = resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return []
    urls: List[str] = []
    for m in re.finditer(r'(https?://[^\"\s>]+\.(?:jpg|jpeg|png))', html_data, flags=re.I):
        u = m.group(1)
        host = (urlparse(u).hostname or '')
        if 'duckduckgo.com' in host or 'logo' in u:
            continue
        urls.append(u)
        if len(urls) >= max_n:
            break
    return urls


def _image_urls_from_bing(query: str, max_n: int = 8) -> List[str]:
    url = f"https://www.bing.com/images/search?q={quote_plus(query)}"
    try:
        req = Request(url, headers={"User-Agent": UA, "Accept-Language": "ar,en;q=0.8"})
        with contextlib.closing(urlopen(req, timeout=20)) as resp:
            html_data = resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return []
    urls: List[str] = []
    for m in re.finditer(r'"murl":"(https?://[^\"]+)"', html_data):
        u = m.group(1)
        host = (urlparse(u).hostname or '')
        if 'bing.com' in host or 'logo' in u:
            continue
        urls.append(u)
        if len(urls) >= max_n:
            break
    if not urls:
        for m in re.finditer(r'(https?://[^\"\s>]+\.(?:jpg|jpeg|png))', html_data, flags=re.I):
            u = m.group(1)
            host = (urlparse(u).hostname or '')
            if 'bing.com' in host or 'logo' in u:
                continue
            urls.append(u)
            if len(urls) >= max_n:
                break
    return urls

