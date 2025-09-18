from __future__ import annotations

import random
import threading
from typing import Optional
import contextlib
from urllib.request import Request, urlopen

from . import cache as _cache

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def fetch(url: str, *, referer: Optional[str] = None, retry: int = 3, sleep: float = 1.0, use_cache: bool = True) -> str:
    """Fetch URL text as UTF-8 with basic retries and optional cache."""
    last_err: Optional[Exception] = None
    if use_cache:
        got = _cache.get_bytes("html", url)
        if got is not None:
            data, _ctype = got
            try:
                return data.decode("utf-8", errors="ignore")
            except Exception:
                pass
    for attempt in range(retry):
        try:
            req = Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept-Language": "ar,en;q=0.8",
                    "Referer": referer or url,
                },
            )
            with contextlib.closing(urlopen(req, timeout=20)) as resp:
                data = resp.read()
            if use_cache:
                try:
                    _cache.put_bytes("html", url, data, "text/html")
                except Exception:
                    pass
            return data.decode("utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt + 1 < retry:
                import time as _time

                _time.sleep(sleep * (2 ** attempt))
            continue
    assert last_err is not None
    raise last_err


class RateLimiter:
    def __init__(self, interval_sec: float, jitter: float = 0.0, *, time_fn=None, sleep_fn=None):
        self.interval = max(0.0, float(interval_sec))
        self.jitter = max(0.0, float(jitter))
        import time as _time

        self.time_fn = time_fn or _time.monotonic
        self.sleep_fn = sleep_fn or _time.sleep
        self._lock = threading.Lock()
        self._next = self.time_fn()

    def wait(self):
        with self._lock:
            now = self.time_fn()
            delay = max(0.0, self._next - now)
            if delay > 0:
                self.sleep_fn(delay)
                now = self.time_fn()
            factor = 1.0
            if self.jitter > 0:
                factor = random.uniform(1.0 - self.jitter, 1.0 + self.jitter)
            self._next = max(now, self._next) + self.interval * factor
