"""One network context for every yt-dlp call: proxy, config policy, time-outs."""

import pytest

from ytdlp_app.netctx import METADATA_SLEEP_REQUESTS, SOCKET_TIMEOUT_SECONDS, NetworkContext
from ytdlp_app.settings import AppSettings


def context(
    *, proxy: str | None = None, rate: str | None = None, external: bool = False, deno: bool = True
) -> NetworkContext:
    settings = AppSettings()
    settings.download.proxy = proxy
    settings.download.rate_limit = rate
    settings.download.allow_external_config = external
    return NetworkContext(settings, deno)


def value(args: list[str], flag: str) -> str:
    return args[args.index(flag) + 1]


class TestEveryCallShares:
    @pytest.mark.parametrize(
        "make",
        [
            lambda c: c.base_args(),
            lambda c: c.download_args(),
            lambda c: c.listing_args(archive=False),
            lambda c: c.listing_args(archive=True),
            lambda c: c.probe_args(),
        ],
    )
    def test_proxy_config_policy_and_timeout(self, make) -> None:
        args = make(context(proxy="http://user:secret@proxy:3128"))

        assert value(args, "--proxy") == "http://user:secret@proxy:3128"
        assert "--ignore-config" in args
        assert value(args, "--socket-timeout") == str(SOCKET_TIMEOUT_SECONDS)
        assert "--remote-components" in args
        assert args[0] == "--ignore-config"

    def test_no_proxy_no_flag(self) -> None:
        assert "--proxy" not in context().probe_args()

    def test_deno_only_when_available(self) -> None:
        assert "--js-runtime" in context(deno=True).probe_args()
        assert "--js-runtime" not in context(deno=False).probe_args()


class TestConfigPolicy:
    def test_external_config_is_ignored_by_default(self) -> None:
        assert "--ignore-config" in context().download_args()

    def test_opting_in_lets_yt_dlp_read_its_own_config(self) -> None:
        for args in (
            context(external=True).base_args(),
            context(external=True).download_args(),
            context(external=True).listing_args(archive=False),
            context(external=True).probe_args(),
        ):
            assert "--ignore-config" not in args


class TestCallSpecificParts:
    def test_only_downloads_carry_the_speed_limit(self) -> None:
        ctx = context(rate="2M")

        assert value(ctx.download_args(), "--limit-rate") == "2M"
        assert "--limit-rate" not in ctx.listing_args(archive=False)
        assert "--limit-rate" not in ctx.probe_args()

    def test_archive_listing_uses_the_configured_request_wait(self) -> None:
        ctx = context()
        ctx.settings.archive.sleep_requests = 4

        assert value(ctx.listing_args(archive=True), "--sleep-requests") == "4"

    def test_regular_listing_and_probes_are_paced_too(self) -> None:
        ctx = context()

        assert value(ctx.listing_args(archive=False), "--sleep-requests") == (
            f"{METADATA_SLEEP_REQUESTS:g}"
        )
        assert value(ctx.probe_args(), "--sleep-requests") == f"{METADATA_SLEEP_REQUESTS:g}"
