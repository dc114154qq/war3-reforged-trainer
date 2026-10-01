<p align="right"><a href="README.md">中文</a> | <strong>English</strong></p>

# Warcraft III: Reforged Trainer

Source code, version adapter data, test fixtures, and release notes for the Warcraft III: Reforged trainer.

## Current Versions

- **Latest source**: `main` and `master` point to the same maintained source.
- **Latest release**: 2.1.0 beta, tag `v2.1.0-beta`.
- **Latest stable release**: 2.0.9, tag `v2.0.9`.
- **Beta adapters**: the beta attempts support for Warcraft III `3.0.0.24268` and `3.0.1.24323`, selecting the matching adapter from the actual PE build fingerprint.

The beta release notes list verified scope and gaps. Configuration, fixtures, and local Windows transport tests do not replace a real run on a reported external machine or a new game build.

## Repository Layout

- `main`, `master`: synchronized entry points for the maintained source.
- `release/<tag>`: source-only historical branches matching published Git tags, such as `release/v2.0.9` and `release/v2.1.0-beta`.
- `v*`, `hotkeys-v*`: immutable release tags and exact source anchors.
- `profiles/`: adapter data organized by game PE build.
- `war3_services/`, `war3_game_session.py`, `war3_engine_transport.py`: feature services, unified session, and transport backends.
- `tools/`: source, build scripts, and verification tools; temporary compilation results stay in local `build/`.
- `website/`: personal-site pages, translations, and the GitHub Release sync script.

## Build and Release

EXE files are distributed as GitHub Release and personal-site download assets. They are not committed to the source repository's `dist/` or `build/` directories. Before a release:

1. Identify the game build and compare the `GameProfile`, RVAs, object layouts, TLS, Native registry, and calling conventions.
2. Verify the shared session, object resolver, bridge protocol, process restart, map reload, window-thread changes, and object-destruction cache invalidation.
3. Verify resource/unit, ability/item, extended-inventory/equipment, and talent/icon capabilities in order, separating command delivery, state readback, and actual game effect.
4. Run the matching build manifest and EXE self-test before publishing the adapter package.
5. Compare live website files before deployment, preserve announcements, subscriptions, and other tool pages, and verify both language pages and the downloaded EXE SHA256.

The 2.1.0 beta uses a dedicated builder:

```powershell
python tools/build_release_210.py
python tools/build_release_210.py --verify-only
```

See [GitHub Releases](https://github.com/dc114154qq/war3-reforged-trainer/releases) for published assets and the [personal site](https://twomengxi.xyz/trainer/) for downloads.

## 2.0.8 / 2.0.9 External-Machine Repairs

The current architecture line starts from 2.0.7 and integrates the loading, fallback-installation, private-callback-exit, and cleanup repairs for 2.0.8 / 2.0.9 in commit `129c389`. Later adapter work must not restore the old transport path. See [ARCHITECTURE.md](ARCHITECTURE.md) and [AGENTS.md](AGENTS.md) for boundaries and evidence.

## License and Scope

Version-specific adapter and native-execution logic is enabled only for a matching game build. Unknown builds produce read-only diagnostics instead of using old offsets for writes. The third-party MinHook license is in `third_party/minhook/LICENSE.txt`.
