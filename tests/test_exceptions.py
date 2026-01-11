"""Tests for ytdlp_app.exceptions module."""

import pytest

from ytdlp_app.exceptions import (
    CommandExecutionError,
    ConfigurationError,
    DownloadError,
    NetworkError,
    PlaylistError,
    ValidationError,
    YtDlpWrapperError,
)


class TestYtDlpWrapperError:
    """Tests for base exception class."""

    def test_is_exception(self) -> None:
        """Test base class inherits from Exception."""
        assert issubclass(YtDlpWrapperError, Exception)

    def test_can_be_raised(self) -> None:
        """Test exception can be raised and caught."""
        with pytest.raises(YtDlpWrapperError):
            raise YtDlpWrapperError("Test error")

    def test_message_is_preserved(self) -> None:
        """Test exception message is preserved."""
        error = YtDlpWrapperError("Test message")
        assert str(error) == "Test message"


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_inherits_from_base(self) -> None:
        """Test inherits from YtDlpWrapperError."""
        assert issubclass(ConfigurationError, YtDlpWrapperError)

    def test_can_be_caught_as_base(self) -> None:
        """Test can be caught as base exception."""
        with pytest.raises(YtDlpWrapperError):
            raise ConfigurationError("Config error")


class TestCommandExecutionError:
    """Tests for CommandExecutionError."""

    def test_inherits_from_base(self) -> None:
        """Test inherits from YtDlpWrapperError."""
        assert issubclass(CommandExecutionError, YtDlpWrapperError)

    def test_stores_command_details(self) -> None:
        """Test command details are stored."""
        error = CommandExecutionError(
            "Command failed",
            command=["yt-dlp", "--version"],
            return_code=1,
            stderr="Error output",
        )
        assert error.command == ["yt-dlp", "--version"]
        assert error.return_code == 1
        assert error.stderr == "Error output"

    def test_optional_attributes_default_to_none(self) -> None:
        """Test optional attributes default to None."""
        error = CommandExecutionError("Simple error")
        assert error.command is None
        assert error.return_code is None
        assert error.stderr is None


class TestNetworkError:
    """Tests for NetworkError."""

    def test_inherits_from_base(self) -> None:
        """Test inherits from YtDlpWrapperError."""
        assert issubclass(NetworkError, YtDlpWrapperError)


class TestValidationError:
    """Tests for ValidationError."""

    def test_inherits_from_base(self) -> None:
        """Test inherits from YtDlpWrapperError."""
        assert issubclass(ValidationError, YtDlpWrapperError)


class TestPlaylistError:
    """Tests for PlaylistError."""

    def test_inherits_from_base(self) -> None:
        """Test inherits from YtDlpWrapperError."""
        assert issubclass(PlaylistError, YtDlpWrapperError)


class TestDownloadError:
    """Tests for DownloadError."""

    def test_inherits_from_base(self) -> None:
        """Test inherits from YtDlpWrapperError."""
        assert issubclass(DownloadError, YtDlpWrapperError)

    def test_stores_download_details(self) -> None:
        """Test download details are stored."""
        error = DownloadError(
            "Download failed",
            url="https://youtube.com/watch?v=abc",
            reason="Video is private",
        )
        assert error.url == "https://youtube.com/watch?v=abc"
        assert error.reason == "Video is private"

    def test_optional_attributes_default_to_none(self) -> None:
        """Test optional attributes default to None."""
        error = DownloadError("Simple error")
        assert error.url is None
        assert error.reason is None
