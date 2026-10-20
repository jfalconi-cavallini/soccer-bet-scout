"""Disk cache so rebuilds do not re-download settled seasons.

Past seasons are immutable. The current season expires after half a day.
football-data.org calls are also paced at the free-tier limit.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import requests

ROOT = Path("data/cache")
PAST_TTL = 60 * 60 * 24 * 365 * 5
CURRENT_TTL = 60 * 60 * 12
FDORG_GAP = 6.5


class HttpCache:
    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._last_fdorg = 0.0

    def _path(self, key: str) -> Path:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
        safe = "".join(ch if ch.isalnum() else "_" for ch in key)[:80]
        return self.root / f"{safe}_{digest}"

    def get_text(self, key: str, ttl_seconds: float) -> str | None:
        path = self._path(key)
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > ttl_seconds:
            return None
        return path.read_text(encoding="utf-8")

    def put_text(self, key: str, text: str) -> None:
        self._path(key).write_text(text, encoding="utf-8")

    def fetch(
        self,
        url: str,
        *,
        ttl_seconds: float,
        headers: dict | None = None,
        params: dict | None = None,
        timeout: float = 40,
        polite_gap: float = 0.35,
        fdorg: bool = False,
    ) -> str | None:
        # Never let an API key become part of a cache path or filename.
        safe_params = {
            key: value
            for key, value in (params or {}).items()
            if key.lower() not in {"apikey", "api_key", "token"}
        }
        cache_key = url if not safe_params else url + "?" + "&".join(
            f"{key}={value}" for key, value in sorted(safe_params.items())
        )
        cached = self.get_text(cache_key, ttl_seconds)
        if cached is not None:
            return cached
        last_error = "no response"
        for attempt in range(3):
            if fdorg:
                wait = FDORG_GAP - (time.time() - self._last_fdorg)
                if wait > 0:
                    time.sleep(wait)
            elif polite_gap and attempt == 0:
                time.sleep(polite_gap)
            try:
                response = requests.get(url, headers=headers, params=params, timeout=timeout)
            except requests.RequestException as exc:
                last_error = str(exc)
                time.sleep(1.5 * (attempt + 1))
                continue
            if fdorg:
                self._last_fdorg = time.time()
            if response.status_code == 404:
                self.put_text(cache_key, "")
                return ""
            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = f"HTTP {response.status_code}"
                time.sleep(1.5 * (attempt + 1))
                continue
            if response.status_code >= 400:
                print(f"  [net] {url} -> {response.status_code}")
                return None
            text = response.text
            self.put_text(cache_key, text)
            return text
        print(f"  [net] {url} failed: {last_error}")
        return None
