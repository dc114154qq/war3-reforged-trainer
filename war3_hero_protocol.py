"""Current-build hero progression ABI, including reversible level stripping."""
import struct

from war3_selection_protocol import (
    build_work as selection_work,
    decode_work as selection_result,
)

WORK_SIZE = 632
ABI = struct.pack("<3I", 0x2426801C, 216, WORK_SIZE)
_HEADER = "<5Q4I"
SIGNATURES = (
    ("SetHeroLevel", "(Hunit;IB)V"),
    ("UnitStripHeroLevel", "(Hunit;I)B"),
    ("SuspendHeroXP", "(Hunit;B)V"),
    ("IsSuspendedXP", "(Hunit;)B"),
)


def build_work(entries, tls, target=0):
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.signature != signature or entry.name != name:
            raise ValueError("Hero progression signature differs from current ABI: " + name)
        handlers.append(entry.handler)
    work = (
        selection_work(entries)
        + struct.pack(_HEADER, *handlers, tls, target, 0, 0, 0)
        + bytes(96)
    )
    validate_work(work)
    return work


def validate_work(work):
    from war3_selection_protocol import validate_work as selection_validate

    if len(work) != WORK_SIZE:
        raise ValueError(f"Hero batch work must contain {WORK_SIZE} bytes")
    selection_validate(work[:480])
    pointers = struct.unpack_from("<5Q", work, 480)
    target, changed, error, reserved = struct.unpack_from("<4I", work, 520)
    if (
        any(not 0x10000 <= pointer < 0x800000000000 for pointer in pointers)
        or len(set(pointers[:4])) != 4
        or pointers[4] % 8
        or not 0 <= target <= 100000
        or changed
        or error
        or reserved
        or any(work[536:])
    ):
        raise ValueError("Invalid hero batch arguments")


def decode_work(work, expected_count):
    if len(work) != WORK_SIZE:
        raise ValueError("Incomplete hero batch result")
    selection = selection_result(work[:480], expected_count)
    target, changed, error, reserved = struct.unpack_from("<4I", work, 520)
    after = struct.unpack_from("<24i", work, 536)
    rows = [
        dict(row, after=after[index])
        for index, row in enumerate(selection["rows"])
        if row["level"] > 0
    ]
    expected_changed = sum(1 for row in rows if target and row["level"] != target)
    if (
        error
        or reserved
        or not rows
        or changed > len(rows)
        or any(row["after"] != (target or row["level"]) for row in rows)
        or changed != expected_changed
    ):
        raise ValueError(
            f"Hero batch incomplete: error={error}, changed={changed}, heroes={len(rows)}"
        )
    return dict(
        rows=rows,
        changed=changed,
        skipped=selection["count"] - len(rows),
        selection_count=selection["count"],
    )
