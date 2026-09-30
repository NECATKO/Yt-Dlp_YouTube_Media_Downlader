"""Hide proxy credentials wherever text is shown or logged.

A proxy URL may carry a user name and password (``http://user:pass@host:3128``).
yt-dlp needs it verbatim on its command line, so the arguments that really run are
never touched; what is *displayed* (the console, the settings screen, the log, error
messages quoting yt-dlp's output) goes through here first.

Two mechanisms cover it: a pattern for ``scheme://user:password@host`` anywhere in
text, and a small registry of the credentials of the proxy actually configured, which
also catches the scheme-less ``user:password@host:port`` form and a bare password
echoed on its own.
"""

from __future__ import annotations

import re
from urllib.parse import unquote

_MASK = "***"

# scheme://user[:password]@ -- credentials end at the first "@" before the host.
_URL_CREDENTIALS = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)(?P<creds>[^/\s@]+)@")
# user:password@host[:port] with no scheme, as a whole argument.
_BARE_CREDENTIALS = re.compile(r"^(?P<creds>[^\s/@]+:[^\s/@]+)@(?P<host>[^\s/@]+)$")

#: Credentials of the configured proxy, as they may appear in text.
_registered: set[str] = set()


def _mask_creds(creds: str) -> str:
    return f"{_MASK}:{_MASK}" if ":" in creds else _MASK


def mask_proxy(proxy: str) -> str:
    """Return a proxy URL with its user name and password replaced by ``***``."""
    masked = _URL_CREDENTIALS.sub(lambda m: f"{m['scheme']}{_mask_creds(m['creds'])}@", proxy)
    if masked != proxy:
        return masked
    bare = _BARE_CREDENTIALS.match(proxy)
    if bare:
        return f"{_mask_creds(bare['creds'])}@{bare['host']}"
    return proxy


def _secrets_of(proxy: str) -> set[str]:
    """The literal strings that would give the credentials away."""
    found: set[str] = set()
    creds = None
    match = _URL_CREDENTIALS.search(proxy)
    if match:
        creds = match["creds"]
    else:
        bare = _BARE_CREDENTIALS.match(proxy)
        if bare:
            creds = bare["creds"]
    if creds is None:
        return found
    found.add(creds)
    for part in creds.split(":"):
        # Very short parts would blank out ordinary text ("a", "1").
        if len(part) >= 3:
            found.add(part)
            found.add(unquote(part))
    return {s for s in found if len(s) >= 3}


def register_proxy(proxy: str | None) -> None:
    """Remember the configured proxy's credentials so they are hidden in any text."""
    if proxy:
        _registered.update(_secrets_of(proxy))


def clear_registered() -> None:
    """Forget every registered credential (the proxy setting changed)."""
    _registered.clear()


def redact_secrets(text: str) -> str:
    """Hide proxy credentials in free text: URLs, and any registered credential."""
    if not text:
        return text
    out = _URL_CREDENTIALS.sub(lambda m: f"{m['scheme']}{_mask_creds(m['creds'])}@", text)
    for secret in sorted(_registered, key=len, reverse=True):
        out = out.replace(secret, _MASK)
    return out


def display_command(cmd: list[str]) -> list[str]:
    """A copy of a command that is safe to show or log; the original is not changed."""
    shown: list[str] = []
    previous = ""
    for arg in cmd:
        if previous == "--proxy":
            shown.append(mask_proxy(arg))
        elif arg.startswith("--proxy="):
            shown.append("--proxy=" + mask_proxy(arg.removeprefix("--proxy=")))
        else:
            shown.append(redact_secrets(arg))
        previous = arg
    return shown
