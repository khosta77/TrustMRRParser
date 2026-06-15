from __future__ import annotations

import time
from typing import Iterator

import requests

BASE_URL = "https://trustmrr.com/api/v1"
MAX_PAGE_SIZE = 50


class TrustMRRError(RuntimeError):
    pass


class StartupNotFound(TrustMRRError):
    def __init__(self, slug: str) -> None:
        super().__init__(f"startup not found: {slug}")
        self.slug = slug


class TrustMRRClient:
    def __init__(
        self,
        api_key: str,
        *,
        proxy: str,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 4,
        safety_buffer: int = 1,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if not proxy:
            raise ValueError("proxy is required")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._safety_buffer = safety_buffer
        self._session = requests.Session()
        self._session.proxies.update({"http": proxy, "https": proxy})
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "trustmrr-scraper/0.1",
            }
        )

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "TrustMRRClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _respect_rate_limit(self, headers: requests.structures.CaseInsensitiveDict) -> None:
        remaining = headers.get("x-ratelimit-remaining")
        reset = headers.get("x-ratelimit-reset")
        if remaining is None or reset is None:
            return
        if int(remaining) > self._safety_buffer:
            return
        wait = int(reset) / 1000 - time.time()
        if wait > 0:
            time.sleep(wait + 0.5)

    def _request(self, path: str, params: dict | None = None) -> dict:
        url = f"{self._base_url}{path}"
        for attempt in range(1, self._max_retries + 1):
            response = self._session.get(url, params=params, timeout=self._timeout)
            if response.status_code == 429:
                reset = response.headers.get("x-ratelimit-reset")
                wait = (int(reset) / 1000 - time.time()) if reset else 5.0 * attempt
                time.sleep(max(wait, 1.0) + 0.5)
                continue
            if response.status_code == 404:
                raise StartupNotFound(path.rsplit("/", 1)[-1])
            if response.status_code >= 500:
                time.sleep(2.0 * attempt)
                continue
            if response.status_code != 200:
                raise TrustMRRError(f"{response.status_code} {url}: {response.text[:200]}")
            self._respect_rate_limit(response.headers)
            return response.json()
        raise TrustMRRError(f"exhausted retries: {url}")

    def list_page(self, page: int, limit: int = MAX_PAGE_SIZE, **filters: str) -> dict:
        params = {"page": page, "limit": min(limit, MAX_PAGE_SIZE), **filters}
        return self._request("/startups", params)

    def iter_startups(self, limit: int = MAX_PAGE_SIZE, **filters: str) -> Iterator[dict]:
        page = 1
        while True:
            payload = self.list_page(page, limit=limit, **filters)
            data = payload.get("data", [])
            for item in data:
                yield item
            if not payload.get("meta", {}).get("hasMore") or not data:
                return
            page += 1

    def total_count(self, **filters: str) -> int:
        payload = self.list_page(1, limit=1, **filters)
        return int(payload.get("meta", {}).get("total", 0))

    def get_startup(self, slug: str) -> dict:
        return self._request(f"/startups/{slug}")["data"]
