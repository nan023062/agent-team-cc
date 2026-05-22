"""GitHub Releases client (stdlib urllib only).

Repo convention:  REPO = "nan023062/cbim"
Asset convention: cbim-kernel-{version}.tar.gz  per release tag v{version}
"""
from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

REPO = "nan023062/cbim"
_API_BASE = "https://api.github.com"
_GH_BASE = "https://github.com"


def _api_get(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "cbim-installer/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(
            "GitHub API error {} for {}: {}".format(exc.code, url, body)
        ) from exc


def fetch_latest_release(repo: str = REPO) -> dict:
    """Return GitHub API response dict for the latest published release."""
    return _api_get("{}/repos/{}/releases/latest".format(_API_BASE, repo))


def fetch_release(version: str, repo: str = REPO) -> dict:
    """Return GitHub API response dict for a specific release tag."""
    tag = "v{}".format(version) if not version.startswith("v") else version
    return _api_get("{}/repos/{}/releases/tags/{}".format(_API_BASE, repo, tag))


def latest_version(repo: str = REPO) -> str:
    """Return the latest release version string, without leading 'v'."""
    data = fetch_latest_release(repo)
    tag = data.get("tag_name", "")
    return tag.lstrip("v")


def asset_url(version: str, repo: str = REPO) -> str:
    """Return the download URL for the kernel tarball for the given version."""
    bare = version[1:] if version.startswith("v") else version
    return "{}/{}/releases/download/v{}/cbim-kernel-{}.tar.gz".format(
        _GH_BASE, repo, bare, bare
    )


def download_tarball(version: str, dest_dir: Path, repo: str = REPO) -> Path:
    """Download the kernel tarball for *version* into *dest_dir*.

    Returns the path to the downloaded file.  Prints progress to stdout.
    Uses chunked streaming to avoid loading the whole tarball into memory.
    """
    url = asset_url(version, repo)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / "cbim-kernel-{}.tar.gz".format(version)

    print("[cbim] downloading {} ...".format(url))
    req = urllib.request.Request(url, headers={"User-Agent": "cbim-installer/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = resp.headers.get("Content-Length")
            total_mb = " ({:.1f} MB)".format(int(total) / 1_048_576) if total else ""
            print("[cbim] saving to {}{}".format(dest_file.name, total_mb))
            with dest_file.open("wb") as out:
                shutil.copyfileobj(resp, out)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            "download failed (HTTP {}): {}".format(exc.code, url)
        ) from exc

    size_mb = dest_file.stat().st_size / 1_048_576
    print("[cbim] downloaded {:.1f} MB".format(size_mb))
    return dest_file
