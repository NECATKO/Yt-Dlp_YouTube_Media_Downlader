"""Tests for the message lookup."""

from ytdlp_app.i18n import t


def test_a_known_key_gives_its_message() -> None:
    assert t("label_yes") == "Yes"


def test_an_unknown_key_is_returned_as_is() -> None:
    assert t("no_such_key_anywhere") == "no_such_key_anywhere"


def test_placeholders_are_filled() -> None:
    assert "3" in t("outcome_completed", count=3)


def test_a_missing_placeholder_value_does_not_raise() -> None:
    assert t("outcome_completed") == t("outcome_completed")
