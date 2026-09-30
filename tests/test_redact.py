"""Proxy credentials must not reach the console, the settings screen or a log."""

import pytest

from ytdlp_app import redact
from ytdlp_app.logging_utils import append_log, log_error
from ytdlp_app.redact import display_command, mask_proxy, redact_secrets, register_proxy


@pytest.fixture(autouse=True)
def _clean_registry():
    redact.clear_registered()
    yield
    redact.clear_registered()


class TestMaskProxy:
    @pytest.mark.parametrize(
        ("proxy", "masked"),
        [
            ("http://alice:hunter2@proxy.example:3128", "http://***:***@proxy.example:3128"),
            ("socks5://alice:hunter2@10.0.0.1:1080", "socks5://***:***@10.0.0.1:1080"),
            ("http://alice@proxy.example:3128", "http://***@proxy.example:3128"),
            ("alice:hunter2@proxy.example:3128", "***:***@proxy.example:3128"),
            ("http://alice:p%40ss:word@proxy:1", "http://***:***@proxy:1"),
        ],
    )
    def test_the_user_and_the_password_are_hidden(self, proxy: str, masked: str) -> None:
        assert mask_proxy(proxy) == masked

    @pytest.mark.parametrize("proxy", ["http://proxy:3128", "proxy:3128", "socks5://h:1", ""])
    def test_a_proxy_without_credentials_is_shown_as_is(self, proxy: str) -> None:
        assert mask_proxy(proxy) == proxy


class TestRedactSecrets:
    def test_urls_with_credentials_anywhere_in_text(self) -> None:
        text = "ProxyError: Unable to connect to proxy ('http://bob:s3cret@proxy:8080') failed"

        out = redact_secrets(text)

        assert "s3cret" not in out and "bob" not in out
        assert "http://***:***@proxy:8080" in out

    def test_a_registered_proxy_is_hidden_even_without_a_scheme(self) -> None:
        register_proxy("alice:hunter2@proxy.example:3128")

        out = redact_secrets("failed to reach alice:hunter2@proxy.example:3128 (hunter2)")

        assert "hunter2" not in out and "alice" not in out

    def test_ordinary_text_is_untouched(self) -> None:
        text = "[download] 42.0% of 10MiB at 1MiB/s https://www.youtube.com/watch?v=x@y"

        assert redact_secrets(text) == text

    def test_an_email_style_address_in_a_title_is_left_alone(self) -> None:
        assert redact_secrets("[download] Destination: talk with a@b.com.mp4") == (
            "[download] Destination: talk with a@b.com.mp4"
        )


class TestDisplayCommand:
    def test_only_the_display_copy_is_masked(self) -> None:
        cmd = ["yt-dlp", "--proxy", "http://bob:s3cret@proxy:8080", "https://youtu.be/x"]

        shown = display_command(cmd)

        assert shown == ["yt-dlp", "--proxy", "http://***:***@proxy:8080", "https://youtu.be/x"]
        assert cmd[2] == "http://bob:s3cret@proxy:8080"

    def test_the_equals_form_is_masked_too(self) -> None:
        assert display_command(["yt-dlp", "--proxy=http://bob:pw@h:1"]) == [
            "yt-dlp",
            "--proxy=http://***:***@h:1",
        ]

    def test_a_scheme_less_proxy_argument_is_masked(self) -> None:
        assert display_command(["yt-dlp", "--proxy", "bob:pw@h:1"])[2] == "***:***@h:1"


class TestLogsAreScrubbed:
    def test_append_log_masks_credentials(self, tmp_path) -> None:
        log = tmp_path / "x.log"

        append_log(log, "CMD: yt-dlp --proxy http://bob:s3cret@proxy:8080 url\n")

        assert "s3cret" not in log.read_text(encoding="utf-8")

    def test_log_error_masks_console_and_log(self, tmp_path, capsys) -> None:
        register_proxy("http://bob:s3cret@proxy:8080")
        log = tmp_path / "x.log"

        log_error(log, "failed via http://bob:s3cret@proxy:8080", RuntimeError("bob:s3cret@proxy"))

        assert "s3cret" not in capsys.readouterr().out
        assert "s3cret" not in log.read_text(encoding="utf-8")
