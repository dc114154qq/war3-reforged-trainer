#!/usr/bin/env python3
"""Mirror GitHub release executables and build the website release index."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_REPOSITORY = "dc114154qq/war3-reforged-trainer"
DEFAULT_COMPATIBILITY = "Warcraft III 2.0.4.23745"
HOTKEY_TAG_PREFIX = "hotkeys-"
USER_AGENT = "war3-release-mirror/1.0"


def request_json(url: str) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=45) as response:
        return json.load(response)


def load_github_releases(repository: str) -> list[dict[str, Any]]:
    releases: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = request_json(
            f"https://api.github.com/repos/{repository}/releases?per_page=100&page={page}"
        )
        if not isinstance(batch, list):
            raise RuntimeError("GitHub Releases API returned an unexpected response")
        releases.extend(batch)
        if len(batch) < 100:
            return releases
        page += 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, destination: Path, expected_size: int | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and (not expected_size or destination.stat().st_size == expected_size):
        destination.chmod(0o644)
        return

    request = Request(url, headers={"User-Agent": USER_AGENT})
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".part", dir=destination.parent
    )
    try:
        with os.fdopen(file_descriptor, "wb") as output, urlopen(request, timeout=180) as response:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        temporary_path = Path(temporary_name)
        if expected_size and temporary_path.stat().st_size != expected_size:
            raise RuntimeError(
                f"size mismatch for {destination.name}: "
                f"expected {expected_size}, got {temporary_path.stat().st_size}"
            )
        temporary_path.chmod(0o644)
        os.replace(temporary_path, destination)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def normalize_manual_release(entry: dict[str, Any], downloads_dir: Path) -> dict[str, Any]:
    result = dict(entry)
    asset = dict(result.get("asset") or {})
    filename = Path(str(asset.get("name", ""))).name
    if not filename:
        raise RuntimeError(f"manual release {result.get('tag', '<unknown>')} has no asset name")
    local_file = downloads_dir / filename
    if not local_file.is_file():
        raise RuntimeError(f"manual release file is missing: {local_file}")
    asset.update(
        {
            "name": filename,
            "url": f"/downloads/{filename}",
            "size": local_file.stat().st_size,
            "sha256": sha256_file(local_file),
        }
    )
    result["asset"] = asset
    result["source"] = "manual"
    return result


def normalize_github_release(
    release: dict[str, Any], downloads_dir: Path, download_assets: bool
) -> dict[str, Any] | None:
    assets = [
        asset
        for asset in release.get("assets", [])
        if str(asset.get("name", "")).lower().endswith(".exe")
    ]
    if not assets:
        return None
    asset = assets[0]
    filename = Path(str(asset["name"])).name
    local_file = downloads_dir / filename
    if download_assets:
        download_file(str(asset["browser_download_url"]), local_file, int(asset.get("size") or 0))
    if not local_file.is_file():
        raise RuntimeError(f"GitHub release file is missing: {local_file}")

    api_digest = str(asset.get("digest") or "")
    expected_digest = api_digest.removeprefix("sha256:") if api_digest.startswith("sha256:") else ""
    actual_digest = sha256_file(local_file)
    if expected_digest and actual_digest.lower() != expected_digest.lower():
        raise RuntimeError(f"SHA256 mismatch for {filename}")

    return {
        "tag": release["tag_name"],
        "name": release.get("name") or release["tag_name"],
        "published_at": release.get("published_at") or release.get("created_at"),
        "compatibility": DEFAULT_COMPATIBILITY,
        "body": release.get("body") or "该版本未提供更新说明。",
        "source": "github",
        "source_url": release.get("html_url"),
        "asset": {
            "name": filename,
            "url": f"/downloads/{filename}",
            "size": local_file.stat().st_size,
            "sha256": actual_digest,
        },
    }


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        Path(temporary_name).chmod(0o644)
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def release_index(repository: str, releases: list[dict[str, Any]]) -> dict[str, Any]:
    if not releases:
        raise RuntimeError("No releases were found")

    from datetime import datetime, timezone

    ordered = sorted(
        releases,
        key=lambda release: str(release.get("published_at") or ""),
        reverse=True,
    )
    return {
        "repository": repository,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "release_count": len(ordered),
        "latest": ordered[0]["tag"],
        "releases": ordered,
    }


def build_indexes(
    site_root: Path, repository: str, download_assets: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    manual_path = site_root / "manual-releases.json"
    downloads_dir = site_root / "downloads"
    manual_data = json.loads(manual_path.read_text(encoding="utf-8"))
    manual_releases = {
        entry["tag"]: normalize_manual_release(entry, downloads_dir)
        for entry in manual_data.get("releases", [])
    }

    trainer_github_releases: dict[str, dict[str, Any]] = {}
    hotkey_github_releases: dict[str, dict[str, Any]] = {}
    for release in load_github_releases(repository):
        normalized = normalize_github_release(release, downloads_dir, download_assets)
        if normalized:
            destination = (
                hotkey_github_releases
                if str(normalized["tag"]).startswith(HOTKEY_TAG_PREFIX)
                else trainer_github_releases
            )
            destination[normalized["tag"]] = normalized

    # A published GitHub release is authoritative. Manual entries bridge versions
    # that have a local build but have not been published on GitHub yet.
    trainer_releases = {**manual_releases, **trainer_github_releases}
    return (
        release_index(repository, list(trainer_releases.values())),
        release_index(repository, list(hotkey_github_releases.values())),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory containing manual-releases.json and the downloads directory",
    )
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Build the index from files that already exist in downloads",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    site_root = args.site_root.resolve()
    try:
        trainer_index, hotkey_index = build_indexes(
            site_root, args.repository, not args.no_download
        )
        atomic_write_json(site_root / "releases.json", trainer_index)
        atomic_write_json(site_root / "hotkey-releases.json", hotkey_index)
    except (HTTPError, URLError, OSError, ValueError, RuntimeError) as error:
        print(f"release sync failed: {error}")
        return 1
    print(
        f"synced {trainer_index['release_count']} trainer releases "
        f"and {hotkey_index['release_count']} hotkey releases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
