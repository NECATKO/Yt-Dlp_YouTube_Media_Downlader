"""Tests for ytdlp_app.speedtest. Nothing here reaches the network."""

import urllib.error
import urllib.request
from typing import Any

import pytest

from ytdlp_app import speedtest
from ytdlp_app.speedtest import MAX_BYTES, MAX_SECONDS, measure_speed

CHUNK = b"x" * 65_536


class _Response:
    """A response that serves chunks until told to stop, counting the reads."""

    def __init__(self, chunks: int | None = None) -> None:
        self.remaining = chunks
        self.reads = 0

    def read(self, _size: int = -1) -> bytes:
        self.reads += 1
        if self.remaining is None:
            return CHUNK
        if self.remaining == 0:
            return b""
        self.remaining -= 1
        return CHUNK

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None


class _Clock:
    """A clock that advances a fixed step on every call."""

    def __init__(self, step: float) -> None:
        self.now = -step
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


def _opener(response: _Response, seen: list[tuple[str, float]] | None = None):
    def open_url(request: urllib.request.Request, timeout: float) -> _Response:
        if seen is not None:
            seen.append((request.full_url, timeout))
        return response

    return open_url


def test_returns_bytes_per_second() -> None:
    response = _Response(chunks=10)
    speed = measure_speed(None, open_url=_opener(response), clock=_Clock(0.1))

    assert speed is not None
    assert speed > 0


def test_asks_for_the_test_url_with_a_timeout() -> None:
    seen: list[tuple[str, float]] = []
    measure_speed(None, open_url=_opener(_Response(chunks=1), seen), clock=_Clock(0.1))

    ((url, timeout),) = seen
    assert url == speedtest.SPEED_TEST_URL
    assert timeout > 0


def test_stops_at_the_byte_cap() -> None:
    response = _Response(chunks=None)
    measure_speed(None, open_url=_opener(response), clock=_Clock(0.0001))

    assert response.reads <= MAX_BYTES // len(CHUNK) + 1


def test_stops_at_the_time_cap() -> None:
    response = _Response(chunks=None)
    # Each clock call advances 2 s: the cap is reached after a few reads.
    measure_speed(None, open_url=_opener(response), clock=_Clock(2.0))

    assert response.reads <= MAX_SECONDS // 2 + 2


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("no route"),
        TimeoutError("slow"),
        ConnectionResetError("reset"),
        ValueError("bad url"),
    ],
)
def test_network_errors_mean_unknown(error: Exception) -> None:
    def failing(_request: urllib.request.Request, _timeout: float) -> _Response:
        raise error

    assert measure_speed(None, open_url=failing, clock=_Clock(0.1)) is None


def test_an_empty_body_means_unknown() -> None:
    assert measure_speed(None, open_url=_opener(_Response(chunks=0)), clock=_Clock(0.1)) is None


@pytest.mark.parametrize("proxy", ["socks5://h:1080", "SOCKS5H://h:1080", " socks4://h:1"])
def test_socks_proxies_are_not_measured(proxy: str) -> None:
    called: list[bool] = []

    def open_url(_request: urllib.request.Request, _timeout: float) -> _Response:
        called.append(True)
        return _Response(chunks=1)

    assert measure_speed(proxy, open_url=open_url, clock=_Clock(0.1)) is None
    assert called == []


def test_a_keyboard_interrupt_is_not_swallowed() -> None:
    def interrupted(_request: urllib.request.Request, _timeout: float) -> _Response:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        measure_speed(None, open_url=interrupted, clock=_Clock(0.1))


@pytest.mark.parametrize(
    ("proxy", "expected"),
    [
        ("host:3128", "http://host:3128"),
        ("http://h:1", "http://h:1"),
        ("https://h:1", "https://h:1"),
    ],
)
def test_proxy_without_a_scheme_is_treated_as_http(proxy: str, expected: str) -> None:
    assert speedtest._normalize_proxy(proxy) == expected
