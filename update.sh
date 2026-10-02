#!/bin/bash
# update.sh - transactional updater for ytdlp-downloader (Linux and macOS)
#
# Usage: ./update.sh [--check-only] [--auto] [--quiet]
#   (no option)   ask, then update the app and offer to update yt-dlp
#   --check-only  only say whether a newer release exists
#   --auto        for unattended use (a scheduled task, a wrapper): install a newer release
#                 without asking, never fail (always exits 0), stay quiet otherwise.
#                 run.sh does not call it; on Linux/macOS updating is on request
#
# The app package is replaced as one transaction:
#   1. the release ZIP is downloaded and unpacked into a temporary folder inside this one,
#   2. the new package is checked (expected files, a version that matches the release and
#      is newer than the installed one, and that it imports) WITHOUT touching the install,
#   3. every file to replace is first copied next to its place, and only when all of those
#      copies exist is each old file moved into a backup folder and the new one moved in,
#   4. the version in app_version.txt is written last, so it never claims a version that
#      was not installed,
#   5. any failure puts every moved file back and leaves the previous version running.
# The previous version stays in .previous-version/ afterwards. An update that was killed
# half way is undone the next time this script starts.
#
# config.json, logs/, archives/, downloads/, cache/, runtime/ and .venv/ are never touched.
# The runtime components (Python, ffmpeg, Deno) are verified separately, by install.sh,
# against the SHA-256 pins in runtime.lock; this script only checks the app package.

set -u

# Configuration
GITHUB_OWNER="NECATKO"
GITHUB_REPO="Yt-Dlp_YouTube_Media_Downlader"
ASSET_NAME="YtDlpDownloader-Portable.zip"
API_URL="${YTDLP_UPDATE_API:-https://api.github.com/repos/$GITHUB_OWNER/$GITHUB_REPO/releases/latest}"
NET_TIMEOUT=20
DOWNLOAD_TIMEOUT=900

# What an update replaces. Everything else in this folder belongs to the user.
REPLACE_DIRS="ytdlp_app"
REPLACE_FILES="downloader.py pyproject.toml runtime.lock run.sh install.sh update.sh Run.bat install.ps1 update.ps1 README.md LICENSE"

# Files a release must contain to be installable.
REQUIRED_FILES="ytdlp_app/__init__.py ytdlp_app/_version.py downloader.py pyproject.toml runtime.lock"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

LOCK_DIR="$SCRIPT_DIR/.update.lock"
JOURNAL="$SCRIPT_DIR/.update-in-progress"
PREVIOUS_DIR="$SCRIPT_DIR/.previous-version"
HAVE_LOCK=0
WORK_DIR=""

QUIET=0
AUTO=0
CHECK_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --check-only) CHECK_ONLY=1 ;;
        --auto) AUTO=1; QUIET=1 ;;
        --quiet) QUIET=1 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

say() {
    if [[ $QUIET -eq 0 ]]; then
        echo -e "$@"
    fi
}

warn() {
    echo -e "${YELLOW}$*${NC}" >&2
}

fail() {
    echo -e "${RED}ERROR: $*${NC}" >&2
}

cleanup() {
    if [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
        rm -rf "$WORK_DIR"
    fi
    if [[ $HAVE_LOCK -eq 1 ]]; then
        rm -rf "$LOCK_DIR"
        HAVE_LOCK=0
    fi
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT TERM

# ==============================================================================
# Versions
# ==============================================================================

# "v1.2.3" -> "1.2.3"
strip_v() {
    local v="${1#v}"
    echo "${v#V}"
}

is_version() {
    [[ "$(strip_v "$1")" =~ ^[0-9]+(\.[0-9]+)*(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$ ]]
}

# Compare two versions the way semver does; prints -1, 0 or 1.
# 0.10.0 > 0.9.0 (numbers, not text), 1.0.0 > 1.0.0-rc1, 1.0.0-rc2 > 1.0.0-rc1.
version_cmp() {
    local a b core_a core_b pre_a="" pre_b=""
    a="$(strip_v "$1")"
    b="$(strip_v "$2")"
    a="${a%%+*}"
    b="${b%%+*}"
    core_a="${a%%-*}"
    core_b="${b%%-*}"
    [[ "$a" == *-* ]] && pre_a="${a#*-}"
    [[ "$b" == *-* ]] && pre_b="${b#*-}"

    local -a pa pb
    local IFS=.
    read -r -a pa <<< "$core_a"
    read -r -a pb <<< "$core_b"
    local n=${#pa[@]} i x y
    (( ${#pb[@]} > n )) && n=${#pb[@]}
    for (( i = 0; i < n; i++ )); do
        x=$(( 10#${pa[i]:-0} ))
        y=$(( 10#${pb[i]:-0} ))
        if (( x > y )); then echo 1; return; fi
        if (( x < y )); then echo -1; return; fi
    done

    if [[ -z "$pre_a" && -z "$pre_b" ]]; then echo 0; return; fi
    if [[ -z "$pre_a" ]]; then echo 1; return; fi   # a release outranks its pre-releases
    if [[ -z "$pre_b" ]]; then echo -1; return; fi

    local -a ia ib
    read -r -a ia <<< "$pre_a"
    read -r -a ib <<< "$pre_b"
    n=${#ia[@]}
    (( ${#ib[@]} > n )) && n=${#ib[@]}
    local ida idb
    for (( i = 0; i < n; i++ )); do
        ida="${ia[i]-}"
        idb="${ib[i]-}"
        if [[ -z "$ida" ]]; then echo -1; return; fi   # fewer identifiers is lower
        if [[ -z "$idb" ]]; then echo 1; return; fi
        if [[ "$ida" =~ ^[0-9]+$ && "$idb" =~ ^[0-9]+$ ]]; then
            if (( 10#$ida > 10#$idb )); then echo 1; return; fi
            if (( 10#$ida < 10#$idb )); then echo -1; return; fi
        elif [[ "$ida" =~ ^[0-9]+$ ]]; then
            echo -1; return                              # numbers sort before words
        elif [[ "$idb" =~ ^[0-9]+$ ]]; then
            echo 1; return
        elif [[ "$ida" > "$idb" ]]; then
            echo 1; return
        elif [[ "$ida" < "$idb" ]]; then
            echo -1; return
        fi
    done
    echo 0
}

# The installed version in tag form ("v1.2.3").
get_current_version() {
    if [[ -f "app_version.txt" ]]; then
        tr -d '[:space:]' < app_version.txt
    else
        echo "unknown"
    fi
}

# ==============================================================================
# Network
# ==============================================================================

fetch_text() {
    local url="$1"
    if command -v curl &> /dev/null; then
        curl -fsSL --max-time "$NET_TIMEOUT" "$url"
    elif command -v wget &> /dev/null; then
        wget -qO- --timeout="$NET_TIMEOUT" "$url"
    else
        return 1
    fi
}

fetch_file() {
    local url="$1" out="$2"
    if command -v curl &> /dev/null; then
        curl -fL --retry 2 --max-time "$DOWNLOAD_TIMEOUT" -o "$out" "$url"
    elif command -v wget &> /dev/null; then
        wget -q --timeout="$NET_TIMEOUT" -O "$out" "$url"
    else
        return 1
    fi
}

# Pull one string field out of the (pretty-printed) release JSON: the first match.
json_field() {
    local json="$1" key="$2"
    printf '%s' "$json" | grep -o "\"$key\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | head -1 \
        | sed 's/.*:[[:space:]]*"\(.*\)"$/\1/'
}

# The download URL of a release asset by exact file name, or nothing.
asset_url() {
    local json="$1" name="$2"
    printf '%s' "$json" | grep -o "\"browser_download_url\"[[:space:]]*:[[:space:]]*\"[^\"]*/$name\"" \
        | head -1 | sed 's/.*:[[:space:]]*"\(.*\)"$/\1/'
}

sha256_of() {
    if command -v sha256sum &> /dev/null; then
        sha256sum "$1" | awk '{ print $1 }'
    elif command -v shasum &> /dev/null; then
        shasum -a 256 "$1" | awk '{ print $1 }'
    else
        return 1
    fi
}

# ==============================================================================
# Unpacking
# ==============================================================================

# Tools that can unpack a ZIP, in order of preference. YTDLP_UPDATE_ZIP_TOOLS overrides
# the list (used by the tests).
zip_tools() {
    echo "${YTDLP_UPDATE_ZIP_TOOLS:-unzip runtime-python python3 bsdtar}"
}

# The interpreter to test packages with: the app's own first (absolute, so it survives a cd).
python_for_checks() {
    if [[ -x "$SCRIPT_DIR/runtime/python/bin/python3" ]]; then
        echo "$SCRIPT_DIR/runtime/python/bin/python3"
    elif [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
        echo "$SCRIPT_DIR/.venv/bin/python"
    elif command -v python3 &> /dev/null; then
        command -v python3
    fi
}

# The first available unpacker's name, or nothing.
find_zip_tool() {
    local tool
    for tool in $(zip_tools); do
        case "$tool" in
            unzip)          command -v unzip &> /dev/null && { echo unzip; return; } ;;
            runtime-python) [[ -x "runtime/python/bin/python3" ]] && { echo runtime-python; return; } ;;
            python3)        command -v python3 &> /dev/null && { echo python3; return; } ;;
            bsdtar)         command -v bsdtar &> /dev/null && { echo bsdtar; return; } ;;
        esac
    done
}

unpack_zip() {
    local tool="$1" zip="$2" dest="$3"
    case "$tool" in
        unzip)          unzip -q "$zip" -d "$dest" ;;
        runtime-python) runtime/python/bin/python3 -s -m zipfile -e "$zip" "$dest" ;;
        python3)        python3 -m zipfile -e "$zip" "$dest" ;;
        bsdtar)         bsdtar -xf "$zip" -C "$dest" ;;
        *)              return 1 ;;
    esac
}

# The folder inside an unpacked release that holds downloader.py (the ZIP may carry one
# top-level folder or none).
find_package_root() {
    local base="$1" candidate
    if [[ -f "$base/downloader.py" ]]; then
        echo "$base"
        return
    fi
    for candidate in "$base"/*/; do
        if [[ -f "${candidate}downloader.py" ]]; then
            echo "${candidate%/}"
            return
        fi
    done
}

# ==============================================================================
# Verifying a package (before anything is changed)
# ==============================================================================

# Version literal of a package, from ytdlp_app/_version.py.
package_version() {
    sed -n 's/^__version__[[:space:]]*=[[:space:]]*["'"'"']\([^"'"'"']*\)["'"'"'].*/\1/p' \
        "$1/ytdlp_app/_version.py" | head -1
}

# Returns 0 when the package in $1 can be installed as release $2 over version $3.
validate_package() {
    local root="$1" tag="$2" current="$3" file version py

    for file in $REQUIRED_FILES; do
        if [[ ! -f "$root/$file" ]]; then
            fail "The downloaded package is incomplete: $file is missing."
            return 1
        fi
    done

    version="$(package_version "$root")"
    if [[ -z "$version" ]] || [[ "$(strip_v "$version")" != "$(strip_v "$tag")" ]]; then
        fail "The package says it is version '${version:-unknown}', not the release $tag."
        return 1
    fi
    if [[ -f "$root/app_version.txt" ]]; then
        if [[ "$(tr -d '[:space:]' < "$root/app_version.txt")" != "$tag" ]]; then
            fail "app_version.txt in the package does not match the release $tag."
            return 1
        fi
    fi

    if [[ "$(version_cmp "$tag" "$current")" != "1" ]]; then
        fail "Release $tag is not newer than the installed $current; not installing it."
        return 1
    fi

    py="$(python_for_checks)"
    if [[ -n "$py" ]]; then
        if ! ( cd "$root" && PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
                "$py" -s -c "import sys; sys.path.insert(0, '.'); import ytdlp_app, ytdlp_app.app" \
                > /dev/null 2>&1 ); then
            fail "The new package does not start under this Python; keeping the installed version."
            return 1
        fi
    else
        warn "No Python found to test the new package with; skipping that check."
    fi
    return 0
}

# ==============================================================================
# The transaction
# ==============================================================================

# The journal: its first line is the backup folder (all an older version wrote), and each
# "+<name>" line after it is an item the update added that did not exist before.
journal_backup() {
    head -n 1 "$JOURNAL"
}

journal_added() {
    sed -n 's/^+//p' "$JOURNAL"
}

# Whether a name is one an update may install (so a damaged journal cannot delete anything
# of the user's).
is_replaced_item() {
    local name="$1" item
    for item in $REPLACE_DIRS $REPLACE_FILES app_version.txt; do
        [[ "$name" == "$item" ]] && return 0
    done
    return 1
}

# Put the previous version back: remove what the update added, then move every file in the
# backup folder back. Restored files leave the backup, so running it again after a partial
# failure only moves what is still missing. Returns 1 when anything could not be restored.
restore_from_backup() {
    local backup="$1" entry name status=0
    while IFS= read -r name; do
        [[ -n "$name" ]] && is_replaced_item "$name" || continue
        [[ -e "$backup/$name" ]] && continue
        rm -rf "${SCRIPT_DIR:?}/$name" || status=1
    done < <(journal_added)
    shopt -s dotglob nullglob
    for entry in "$backup"/*; do
        name="$(basename "$entry")"
        # A test hook: fail restoring $name, to exercise a rollback that fails itself.
        if [[ "${YTDLP_UPDATE_RESTORE_FAULT_AT:-}" == "$name" ]]; then
            status=1
            continue
        fi
        rm -rf "${SCRIPT_DIR:?}/$name"
        if ! mv "$entry" "$SCRIPT_DIR/$name"; then
            status=1
        fi
    done
    shopt -u dotglob nullglob
    return $status
}

# A previous update that never finished (or whose rollback failed): undo it. The journal
# and the backup stay until everything is back, so this can simply be run again.
recover_interrupted() {
    [[ -f "$JOURNAL" ]] || return 0
    local backup
    backup="$(journal_backup)"
    if [[ -n "$backup" && -d "$backup" ]]; then
        warn "A previous update was interrupted; restoring the previous version..."
        if ! restore_from_backup "$backup"; then
            fail "Could not restore everything; the files are in $backup. Run update.sh again to retry."
            return 1
        fi
        rm -rf "$backup"
    fi
    rm -f "$JOURNAL"
    rm -rf "$SCRIPT_DIR"/.update-new-*
    say "${GREEN}The previous version was restored.${NC}"
}

# Undo a half-made update. Called from apply_update, whose $backup and $staging it uses
# (bash locals are visible to the functions a function calls).
abort_update() {
    fail "$1"
    warn "Rolling back to the previous version..."
    rm -rf "$staging" "$SCRIPT_DIR/.app_version.new"
    if ! restore_from_backup "$backup"; then
        # Keep the journal and the backup: they are the only way back now.
        fail "The rollback was incomplete; the old files are in $backup. Run update.sh again to finish restoring them; do not start the app before that."
        return 1
    fi
    rm -f "$JOURNAL"
    rm -rf "$backup"
    return 1
}

# Install the package in $1 as release $2. Rolls back completely on any failure.
apply_update() {
    local root="$1" tag="$2" stamp backup staging item py

    stamp="$(date +%Y%m%d-%H%M%S)-$$"
    backup="$SCRIPT_DIR/.update-backup-$stamp"
    staging="$SCRIPT_DIR/.update-new-$stamp"
    mkdir "$backup" "$staging" || { fail "Cannot create work folders in $SCRIPT_DIR."; return 1; }

    # From here on a crash is recoverable: the journal says where the old files are.
    printf '%s\n' "$backup" > "$JOURNAL.tmp" && mv "$JOURNAL.tmp" "$JOURNAL" \
        || { rm -rf "$backup" "$staging"; fail "Cannot write the update journal."; return 1; }

    # 1) Copy every new file next to its place. Nothing of the install changes yet.
    for item in $REPLACE_DIRS $REPLACE_FILES; do
        [[ -e "$root/$item" ]] || continue
        cp -R "$root/$item" "$staging/$item" \
            || { abort_update "Could not copy $item from the new package."; return 1; }
    done

    # 2) Swap: old -> backup, new -> place. Each step is a rename.
    for item in $REPLACE_DIRS $REPLACE_FILES; do
        [[ -e "$staging/$item" ]] || continue
        if [[ -e "$item" || -L "$item" ]]; then
            mv "$item" "$backup/$item" || { abort_update "Could not move $item aside."; return 1; }
        else
            # New in this release: noted before it appears, so a rollback removes it.
            printf '+%s\n' "$item" >> "$JOURNAL" \
                || { abort_update "Cannot write the update journal."; return 1; }
        fi
        # A test hook: fail once the old $item is out of the way, to exercise the rollback.
        if [[ "${YTDLP_UPDATE_FAULT_AT:-}" == "$item" ]]; then
            abort_update "Injected failure while installing $item."
            return 1
        fi
        mv "$staging/$item" "$item" || { abort_update "Could not install $item."; return 1; }
    done
    for item in run.sh install.sh update.sh; do
        if [[ -f "$item" ]]; then chmod +x "$item"; fi
    done

    # 3) The version last, so it only ever names what is really installed.
    if [[ -e app_version.txt ]]; then
        mv app_version.txt "$backup/app_version.txt" \
            || { abort_update "Could not move app_version.txt aside."; return 1; }
    else
        printf '+%s\n' app_version.txt >> "$JOURNAL" \
            || { abort_update "Cannot write the update journal."; return 1; }
    fi
    if ! { printf '%s\n' "$tag" > .app_version.new && mv .app_version.new app_version.txt; }; then
        abort_update "Could not record the new version."
        return 1
    fi

    # 4) The installed copy must start too.
    py="$(python_for_checks)"
    if [[ -n "$py" ]]; then
        if ! "$py" -s -c "import ytdlp_app, ytdlp_app.app" > /dev/null 2>&1; then
            abort_update "The installed package does not start."
            return 1
        fi
    fi

    # Commit: the journal goes away, the old version becomes .previous-version.
    rm -f "$JOURNAL"
    rm -rf "$PREVIOUS_DIR"
    mv "$backup" "$PREVIOUS_DIR" 2> /dev/null || rm -rf "$backup"
    rm -rf "$staging"
    return 0
}

# Download, verify and install the release described by the JSON in $1.
install_release() {
    local release_json="$1" tag="$2" current="$3"
    local zip_url sha_url zip_tool zip_file extract_dir root expected actual

    zip_tool="$(find_zip_tool)"
    if [[ -z "$zip_tool" ]]; then
        fail "Nothing here can unpack a ZIP (looked for: $(zip_tools)). Install unzip (or python3) and try again; nothing was changed."
        return 1
    fi

    zip_url="${YTDLP_UPDATE_ZIP_URL:-$(asset_url "$release_json" "$ASSET_NAME")}"
    if [[ -z "$zip_url" ]]; then
        fail "Release $tag has no $ASSET_NAME asset; nothing was changed."
        return 1
    fi
    sha_url="${YTDLP_UPDATE_SHA_URL:-$(asset_url "$release_json" "$ASSET_NAME.sha256")}"

    # A private work folder inside this one: same file system (renames stay atomic),
    # unique per run (no clash with another run or an old crash).
    WORK_DIR="$(mktemp -d "$SCRIPT_DIR/.update-work-XXXXXX")" || { fail "Cannot create a work folder."; return 1; }
    zip_file="$WORK_DIR/release.zip"
    extract_dir="$WORK_DIR/unpacked"
    mkdir "$extract_dir"

    say "${YELLOW}Downloading $tag...${NC}"
    if ! fetch_file "$zip_url" "$zip_file"; then
        fail "The download failed; nothing was changed."
        return 1
    fi

    # The release checksum, when the release publishes one. Without it the package is
    # only checked structurally (below); runtime components are pinned separately.
    if [[ -n "$sha_url" ]]; then
        expected="$(fetch_text "$sha_url" | awk '{ print tolower($1) }' | head -1)"
        actual="$(sha256_of "$zip_file")"
        if [[ -z "$expected" || -z "$actual" || "$expected" != "$actual" ]]; then
            fail "The download does not match the published SHA-256 checksum; it was discarded."
            return 1
        fi
        say "${GREEN}Checksum verified.${NC}"
    else
        say "${YELLOW}This release publishes no checksum; the package is verified structurally only.${NC}"
    fi

    say "${YELLOW}Unpacking...${NC}"
    if ! unpack_zip "$zip_tool" "$zip_file" "$extract_dir"; then
        fail "The package could not be unpacked; nothing was changed."
        return 1
    fi

    root="$(find_package_root "$extract_dir")"
    if [[ -z "$root" ]]; then
        fail "The package has an unexpected layout (no downloader.py); nothing was changed."
        return 1
    fi

    validate_package "$root" "$tag" "$current" || return 1

    say "${YELLOW}Installing...${NC}"
    apply_update "$root" "$tag" || return 1
    say "${GREEN}Updated to $tag. The previous version is kept in .previous-version/.${NC}"
    return 0
}

# ==============================================================================
# yt-dlp
# ==============================================================================

# What the app installs yt-dlp as (with its extras: curl-cffi is what lets YouTube serve
# subtitles), asked from the installed app so this script never drifts from it.
ytdlp_requirement() {
    local py requirement=""
    py="$(python_for_checks)"
    if [[ -n "$py" ]]; then
        requirement="$("$py" -s -c 'from ytdlp_app.portable import YTDLP_REQUIREMENT as r; print(r)' \
            2> /dev/null)"
    fi
    echo "${requirement:-yt-dlp[default,curl-cffi]}"
}

# Update yt-dlp now, because the user asked. Unlike the weekly check at launch (which carries
# on with the installed copy when offline), a failure here is reported and returns 1.
update_ytdlp() {
    local status
    echo -e "${YELLOW}Updating yt-dlp...${NC}"

    if [[ -x "runtime/python/bin/python3" ]]; then
        PYTHONNOUSERSITE=1 runtime/python/bin/python3 -s -m ytdlp_app.portable update-ytdlp
        status=$?
    elif [[ -f ".venv/bin/pip" ]]; then
        .venv/bin/pip install --upgrade "$(ytdlp_requirement)"
        status=$?
    elif [[ -f ".venv/Scripts/pip.exe" ]]; then
        .venv/Scripts/pip.exe install --upgrade "$(ytdlp_requirement)"
        status=$?
    else
        fail "Virtual environment not found."
        return 1
    fi

    if [[ $status -ne 0 ]]; then
        fail "yt-dlp could not be updated; the installed version is unchanged."
        return 1
    fi
    echo -e "${GREEN}yt-dlp updated successfully!${NC}"
}

# ==============================================================================
# Main
# ==============================================================================

main() {
    local current latest release_json cmp choice

    if ! acquire_lock; then
        [[ $AUTO -eq 1 ]] || fail "Another update is already running (lock: $LOCK_DIR)."
        return $(( AUTO == 1 ? 0 : 1 ))
    fi

    if ! recover_interrupted; then
        return $(( AUTO == 1 ? 0 : 1 ))
    fi

    current="$(get_current_version)"
    if ! is_version "$current"; then
        [[ $AUTO -eq 1 ]] || fail "Cannot read the installed version (app_version.txt says '$current')."
        return $(( AUTO == 1 ? 0 : 1 ))
    fi

    if [[ $CHECK_ONLY -eq 0 && $AUTO -eq 0 ]]; then
        echo -e "${CYAN}========================================${NC}"
        echo -e "${CYAN}  ytdlp-downloader Updater${NC}"
        echo -e "${CYAN}========================================${NC}"
        echo ""
        echo -e "${YELLOW}Current version:${NC} $current"
    fi

    # Offline (or GitHub unreachable) is normal, and must never get in the way of starting.
    release_json="$(fetch_text "$API_URL" 2> /dev/null)"
    latest="$(json_field "$release_json" tag_name)"
    if [[ -z "$latest" ]] || ! is_version "$latest"; then
        [[ $QUIET -eq 1 ]] || echo -e "${YELLOW}Could not check for updates.${NC}"
        latest=""
    fi

    if [[ -n "$latest" ]]; then
        cmp="$(version_cmp "$latest" "$current")"
        if [[ "$cmp" == "1" ]]; then
            if [[ $CHECK_ONLY -eq 1 ]]; then
                echo -e "${YELLOW}Update available: $current -> $latest${NC}"
                return 0
            fi
            if [[ $AUTO -eq 1 ]]; then
                echo -e "${CYAN}Installing update $current -> $latest...${NC}"
                install_release "$release_json" "$latest" "$current" \
                    || warn "The update was not installed; continuing with $current."
                return 0
            fi
            echo -e "${YELLOW}Latest version:${NC} $latest"
            echo -e "${YELLOW}A new version is available!${NC}"
            echo ""
            read -r -p "Download and install update? (y/N): " choice
            if [[ "$choice" =~ ^[Yy]$ ]]; then
                if install_release "$release_json" "$latest" "$current"; then
                    echo -e "${YELLOW}Restart the application to use the new version.${NC}"
                else
                    return 1
                fi
            fi
        elif [[ $CHECK_ONLY -eq 0 && $AUTO -eq 0 ]]; then
            echo -e "${YELLOW}Latest version:${NC} $latest"
            echo -e "${GREEN}You are running the latest version.${NC}"
        fi
    fi

    if [[ $CHECK_ONLY -eq 1 || $AUTO -eq 1 ]]; then
        return 0
    fi

    echo ""

    # Always offer to update yt-dlp
    read -r -p "Update yt-dlp to latest version? (y/N): " choice
    if [[ "$choice" =~ ^[Yy]$ ]]; then
        update_ytdlp || return 1
    fi

    echo ""
    echo -e "${GREEN}Done!${NC}"
    return 0
}

acquire_lock() {
    if mkdir "$LOCK_DIR" 2> /dev/null; then
        printf '%s' "$$" > "$LOCK_DIR/pid"
        HAVE_LOCK=1
        return 0
    fi
    local other
    other="$(cat "$LOCK_DIR/pid" 2> /dev/null || true)"
    if [[ -n "$other" ]] && kill -0 "$other" 2> /dev/null; then
        return 1
    fi
    # The run that held it is gone (killed): the lock is stale.
    rm -rf "$LOCK_DIR"
    if mkdir "$LOCK_DIR" 2> /dev/null; then
        printf '%s' "$$" > "$LOCK_DIR/pid"
        HAVE_LOCK=1
        return 0
    fi
    return 1
}

main "$@"
exit $?
