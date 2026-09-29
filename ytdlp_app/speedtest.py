"""A short connection-speed measurement, used to turn a size estimate into a
time estimate.

It downloads a few seconds' worth of a public test file, so it measures the
line, not YouTube: it cannot see YouTube-specific throttling, and it tells the
test host the user's IP. It goes through the configured proxy, is skipped for
SOCKS proxies (urllib cannot use them) and reports None on any failure, which
callers treat as "speed unknown", never as an error.
"""

from __future__ import annotations

import http.client
import time
import urllib.request
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import IO, cast

#: A public speed-test download endpoint (about 10 MB).
SPEED_TEST_URL = "https://speed.cloudflare.com/__down?bytes=10000000"

#: Stop after this many bytes or seconds, whichever comes first.
MAX_BYTES = 10_000_000
MAX_SECONDS = 5.0

#: Connect/read timeout for the request.
TIMEOUT_SECONDS = 5.0

_CHUNK_BYTES = 65_536

UrlOpener = Callable[[urllib.request.Request, float], AbstractContextManager[IO[bytes]]]


def _is_socks(proxy: str) -> bool:
    return proxy.strip().lower().startswith("socks")


def _normalize_proxy(proxy: str) -> str:
    """yt-dlp accepts 'host:port'; urllib needs a scheme."""
    proxy = proxy.strip()
    return proxy if "://" in proxy else f"http://{proxy}"


def _default_opener(proxy: str | None) -> UrlOpener:
    handlers: list[urllib.request.BaseHandler] = []
    if proxy:
        url = _normalize_proxy(proxy)
        handlers.append(urllib.request.ProxyHandler({"http": url, "https": url}))
    director = urllib.request.build_opener(*handlers)

    def open_url(
        request: urllib.request.Request, timeout: float
    ) -> AbstractContextManager[IO[bytes]]:
        return cast("AbstractContextManager[IO[bytes]]", director.open(request, timeout=timeout))

    return open_url


def measure_speed(
    proxy: str | None,
    *,
    open_url: UrlOpener | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> float | None:
    """Measure the download speed in bytes per second.

    Args:
        proxy: The configured proxy, or None.
        open_url: Opens the request; replaced in tests.
        clock: Monotonic seconds; replaced in tests.

    Returns:
        Bytes per second, or None when it could not be measured.

    Raises:
        KeyboardInterrupt: the user pressed Ctrl+C during the measurement.
    """
    if proxy and _is_socks(proxy):
        return None

    opener = open_url if open_url is not None else _default_opener(proxy)
    request = urllib.request.Request(SPEED_TEST_URL, headers={"User-Agent": "ytdlp-downloader"})
    received = 0
    try:
        start = clock()
        with opener(request, TIMEOUT_SECONDS) as response:
            while received < MAX_BYTES:
                chunk = response.read(_CHUNK_BYTES)
                if not chunk:
                    break
                received += len(chunk)
                if clock() - start >= MAX_SECONDS:
                    break
        elapsed = clock() - start
    except (OSError, http.client.HTTPException, ValueError):
        return None

    if received <= 0 or elapsed <= 0:
        return None
    return received / elapsed
