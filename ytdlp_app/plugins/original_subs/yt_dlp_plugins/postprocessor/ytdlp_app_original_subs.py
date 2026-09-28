"""yt-dlp plugin that keeps only subtitles that exist on YouTube itself.

YouTube offers every auto-generated subtitle machine-translated into dozens of
languages. yt-dlp lists those translations under the plain language code, so
"--sub-langs tr.*" on an English video also matches YouTube's Turkish
translation of it. Translations are generated on request (the URL carries a
"tlang" parameter), are not part of what the channel published and are the
subtitle requests YouTube rate limits first.

"--extractor-args youtube:skip=translated_subs" does not help: it only skips
translations of uploaded subtitles, not of the auto-generated ones.

YouTube also lists the original auto-generated subtitle twice, as "en" and
"en-orig", with the same URL. Only the plain code is kept, so each video
costs one subtitle request per language instead of two.

Archive mode loads this module with --plugin-dirs and runs it with
"--use-postprocessor OriginalSubsOnly:when=video", which is after the
subtitles are selected and before any of them is downloaded.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from yt_dlp.postprocessor.common import PostProcessor


def is_translation(subtitle: dict[str, Any]) -> bool:
    """Tell whether a subtitle entry is a machine translation made by YouTube."""
    url = subtitle.get("url")
    if not isinstance(url, str):
        return False
    return "tlang" in parse_qs(urlparse(url).query)


def is_orig_copy(lang: str, requested: dict[str, dict[str, Any]]) -> bool:
    """Tell whether "<lang>-orig" repeats the "<lang>" entry that is also requested."""
    if not lang.endswith("-orig"):
        return False
    plain = requested.get(lang.removesuffix("-orig"))
    return plain is not None and plain.get("url") == requested[lang].get("url")


class OriginalSubsOnlyPP(PostProcessor):
    """Drop translated and duplicate entries from the subtitles about to be downloaded."""

    def run(self, info: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
        requested = info.get("requested_subtitles")
        if not requested:
            return [], info

        translated = sorted(lang for lang, sub in requested.items() if is_translation(sub))
        copies = sorted(lang for lang in requested if is_orig_copy(lang, requested))
        dropped = {*translated, *copies}
        if dropped:
            info["requested_subtitles"] = {
                lang: sub for lang, sub in requested.items() if lang not in dropped
            }
        if translated:
            self.to_screen(f"Skipping machine-translated subtitles: {', '.join(translated)}")
        if copies:
            self.to_screen(f"Skipping duplicate subtitles: {', '.join(copies)}")
        return [], info
