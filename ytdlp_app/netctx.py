"""The one place that decides which options every yt-dlp call shares.

A download and the playlist listing both talk to YouTube, and they must do so under the
same rules: the proxy the user configured, the same JavaScript runtime, the same network
time-out and the same stance on yt-dlp's own configuration files. Building those
arguments in each caller is how the listing came to ignore the proxy while the download
honoured it.

What differs between the calls stays with the call: a download adds the speed
limit and its retry policy, a listing adds a pacing wait and a time limit
on the whole process (see exec.run_capture), never on a download.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from .settings import AppSettings

#: Seconds a single network read may stall before yt-dlp gives up on it. It bounds
#: a hung connection, not the length of a download.
SOCKET_TIMEOUT_SECONDS: Final = 30

#: Wait between the requests of a regular-mode listing, in seconds.
#: (Archive mode uses its own configured wait.)
METADATA_SLEEP_REQUESTS: Final = 1

#: Time limit for the listing, in seconds. It walks every page of a channel and, in
#: archive mode, waits between them, so it gets a long allowance. Downloads have no
#: overall limit.
LISTING_TIMEOUT_SECONDS: Final = 30 * 60


def js_runtime_args(use_deno: bool) -> list[str]:
    """Build JavaScript runtime arguments for yt-dlp."""
    base = ["--remote-components", "ejs:github"]
    if not use_deno:
        return base
    return ["--js-runtimes", "deno", *base]


@dataclass(frozen=True, slots=True)
class NetworkContext:
    """Arguments shared by every yt-dlp call the app makes.

    Attributes:
        settings: The user's settings (proxy, speed limit, external config policy).
        use_deno: Whether the Deno runtime is available for YouTube's JS challenges.
    """

    settings: AppSettings
    use_deno: bool

    def base_args(self) -> list[str]:
        """Options for every call: config policy, JS runtime, time-out and proxy.

        ``--ignore-config`` comes first unless the user opted in to their own yt-dlp
        configuration files: those can add anything (``--skip-download``,
        ``--extract-audio``, a different output template) and would make the app's
        settings and what yt-dlp does disagree.
        """
        download = self.settings.download
        args: list[str] = []
        if not download.allow_external_config:
            args.append("--ignore-config")
        args += js_runtime_args(self.use_deno)
        args += ["--socket-timeout", str(SOCKET_TIMEOUT_SECONDS)]
        if download.proxy:
            args += ["--proxy", download.proxy]
        return args

    def download_args(self) -> list[str]:
        """Base options plus the download speed limit."""
        args = self.base_args()
        if self.settings.download.rate_limit:
            args += ["--limit-rate", self.settings.download.rate_limit]
        return args

    def listing_args(self, *, archive: bool) -> list[str]:
        """Options for a flat playlist or channel listing."""
        wait = self.settings.archive.sleep_requests if archive else METADATA_SLEEP_REQUESTS
        return [*self.base_args(), "--sleep-requests", f"{wait:g}"]
