"""Build the character set for text that comes from the game rather than from our source.

Names of units, items, abilities and fields are read at runtime, so the UI subset cannot
see them. This collects every Han character from the trainer's Python catalogs and adds
GB2312 level 1 (3755 common characters) as a safety net. The result is committed as
assets-src/fonts/charset-names.txt so builds do not need the trainer repository.

Usage: python -I scripts/fonts/collect_names.py <trainer repository>
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "assets-src" / "fonts" / "charset-names.txt"


def is_han(ch: str) -> bool:
    cp = ord(ch)
    return 0x3400 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF


def gb2312_level1() -> set[str]:
    chars = set()
    for hi in range(0xB0, 0xD8):
        for lo in range(0xA1, 0xFF):
            try:
                chars.add(bytes([hi, lo]).decode("gb2312"))
            except UnicodeDecodeError:
                pass
    return chars


def from_repository(repo: pathlib.Path) -> set[str]:
    chars = set()
    for path in sorted(repo.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        chars.update(ch for ch in text if is_han(ch))
    return chars


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    repo = pathlib.Path(sys.argv[1]).resolve()
    if not (repo / "war3_id_descriptions.py").exists():
        sys.exit(f"{repo} does not look like the trainer repository")
    level1 = gb2312_level1()
    catalog = from_repository(repo)
    chars = level1 | catalog
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(sorted(chars)), encoding="utf-8")
    print(f"GB2312 level 1: {len(level1)}, from catalogs: {len(catalog)}, "
          f"catalog-only: {len(catalog - level1)}, total: {len(chars)} -> {OUT.name}")


if __name__ == "__main__":
    main()
