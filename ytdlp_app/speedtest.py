"""A short connection-speed measurement, used to turn a size estimate into a
time estimate.

It downloads a few seconds' worth of a public test file, so it measures the
line, not YouTube: it cannot see YouTube-specific throttling, and it tells the
test host the user's IP. It goes through the configured proxy, is skipped for
SOCKS proxies (urllib cannot use them) and reports None on any failure, which
callers treat as "speed unknown", never as an error.

The whole measurement is bounded by TOTAL_BUDGET_SECONDS however the connection
behaves: the transfer runs in a worker thread and the caller stops waiting for it at the
budget. (A check made only between reads cannot bound it, because a read that blocks
is exactly the case where it never gets to run.)
"""

from __future__ import annotations

import http.client
import threading
import time
import urllib.request
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import IO, cast

#: A public speed-test download endpoint (about 10 MB).
SPEED_TEST_URL = "https://speed.cloudflare.com/__down?bytes=10000000"

#: Stop after this many bytes or seconds, whichever comes first.
MAX_BYTES = 10_000_000
MAX_SECONDS = 5.0

#: Hard limit on the whole measurement, connect and stalled reads included.
TOTAL_BUDGET_SECONDS = 8.0

#: Connect/read timeout for the request.
TIMEOUT_SECONDS = 5.0

#: Less than this before the budget ends is too little to call a speed.
MIN_MEASURED_BYTES = 65_536

_CHUNK_BYTES = 65_536

#: How often a cancellable measurement looks at its cancel event while it waits.
_CANCEL_POLL = 0.05

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


@dataclass
class _Transfer:
    """What the worker thread has done so far, read by the caller when it stops waiting."""

    start: float = 0.0
    received: int = 0
    elapsed: float | None = None
    stop: bool = False
    #: An exception that is not "the network failed", to be raised in the caller's thread.
    error: BaseException | None = None


def _wait_for(worker: threading.Thread, cancel: threading.Event | None) -> None:
    """Wait for the transfer until the budget runs out; raise KeyboardInterrupt on cancel."""
    if cancel is None:
        worker.join(timeout=TOTAL_BUDGET_SECONDS)
        return
    deadline = time.monotonic() + TOTAL_BUDGET_SECONDS
    while worker.is_alive() and not cancel.is_set():
        left = deadline - time.monotonic()
        if left <= 0:
            return
        worker.join(timeout=min(left, _CANCEL_POLL))
    if cancel.is_set():
        raise KeyboardInterrupt


def measure_speed(
    proxy: str | None,
    *,
    open_url: UrlOpener | None = None,
    clock: Callable[[], float] = time.monotonic,
    cancel: threading.Event | None = None,
) -> float | None:
    """Measure the download speed in bytes per second.

    Args:
        proxy: The configured proxy, or None.
        open_url: Opens the request; replaced in tests.
        clock: Monotonic seconds; replaced in tests.
        cancel: When set (from another thread), the measurement is abandoned as for
            Ctrl+C. None leaves Ctrl+C as the only way to cancel.

    Returns:
        Bytes per second, or None when it could not be measured within
        TOTAL_BUDGET_SECONDS (or the connection gave too little data to say).

    Raises:
        KeyboardInterrupt: the user pressed Ctrl+C (or set ``cancel``) during the
            measurement.
    """
    if proxy and _is_socks(proxy):
        return None

    opener = open_url if open_url is not None else _default_opener(proxy)
    request = urllib.request.Request(SPEED_TEST_URL, headers={"User-Agent": "ytdlp-downloader"})
    transfer = _Transfer()

    def work() -> None:
        try:
            transfer.start = clock()
            with opener(request, TIMEOUT_SECONDS) as response:
                while transfer.received < MAX_BYTES and not transfer.stop:
                    chunk = response.read(_CHUNK_BYTES)
                    if not chunk:
                        break
                    transfer.received += len(chunk)
                    if clock() - transfer.start >= MAX_SECONDS:
                        break
            transfer.elapsed = clock() - transfer.start
        except (OSError, http.client.HTTPException, ValueError):
            transfer.received = 0
        except BaseException as ex:
            transfer.error = ex

    worker = threading.Thread(target=work, name="speed-test", daemon=True)
    worker.start()
    try:
        _wait_for(worker, cancel)
    except BaseException:
        transfer.stop = True
        raise

    if transfer.error is not None:
        raise transfer.error

    if worker.is_alive():
        # Out of time: the worker is a daemon still stuck in a read. What it had received
        # by now is the measurement, if it is enough to mean anything.
        transfer.stop = True
        if transfer.received < MIN_MEASURED_BYTES:
            return None
        elapsed = clock() - transfer.start
    else:
        elapsed = transfer.elapsed if transfer.elapsed is not None else 0.0

    if transfer.received <= 0 or elapsed <= 0:
        return None
    return transfer.received / elapsed
