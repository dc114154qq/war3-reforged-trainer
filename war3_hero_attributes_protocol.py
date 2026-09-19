"""Current-build transactional hero attribute ABI."""
import struct

from war3_selection_protocol import (
    build_work as selection_work,
    decode_work as selection_result,
)

WORK_SIZE = 1144
ABI = struct.pack("<3I", 0x24268030, 216, WORK_SIZE)
SIGNATURES = (
    ("GetHeroStr", "(Hunit;B)I"),
    ("GetHeroAgi", "(Hunit;B)I"),
    ("GetHeroInt", "(Hunit;B)I"),
    ("SetHeroStr", "(Hunit;IB)V"),
    ("SetHeroAgi", "(Hunit;IB)V"),
    ("SetHeroInt", "(Hunit;IB)V"),
)


def build_work(entries, tls, target=None):
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Hero attribute signature differs from current ABI: " + name)
        handlers.append(entry.handler)
    if target is None:
        targets = (0, 0, 0)
        mode = 0
    elif isinstance(target, int) and not isinstance(target, bool):
        targets = (target, target, target)
        mode = 1
    else:
        targets = tuple(target)
        mode = 1
    if len(targets) != 3 or any(
        isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000_000
        for value in targets
    ):
        raise ValueError("Hero attribute targets must contain three integers in 0..1000000000")
    work = (
        selection_work(entries)
        + struct.pack("<7Q8I", *handlers, tls, *targets, 0, 0, 0, 0, mode)
        + bytes(576)
    )
    validate_work(work)
    return work


def validate_work(work):
    from war3_selection_protocol import validate_work as selection_validate

    if len(work) != WORK_SIZE:
        raise ValueError(f"Hero attribute work must contain {WORK_SIZE} bytes")
    selection_validate(work[:480])
    pointers = struct.unpack_from("<7Q", work, 480)
    values = struct.unpack_from("<8I", work, 536)
    targets = values[:3]
    changed, error, completed, rollback_error, mode = values[3:]
    if (
        any(not 0x10000 <= pointer < 0x800000000000 for pointer in pointers)
        or len(set(pointers[:6])) != 6
        or pointers[6] % 8
        or any(target > 1_000_000_000 for target in targets)
        or changed
        or error
        or completed
        or rollback_error
        or mode not in (0, 1)
        or (mode == 0 and any(targets))
        or any(work[568:])
    ):
        raise ValueError("Invalid hero attribute arguments")


def decode_work(work, expected_count):
    if len(work) != WORK_SIZE:
        raise ValueError("Incomplete hero attribute result")
    selection = selection_result(work[:480], expected_count)
    values = struct.unpack_from("<8I", work, 536)
    targets = values[:3]
    changed, error, completed, rollback_error, mode = values[3:]
    before = struct.unpack_from("<72i", work, 568)
    after = struct.unpack_from("<72i", work, 856)
    rows = []
    for index, row in enumerate(selection["rows"]):
        if row["level"] <= 0:
            continue
        start = index * 3
        rows.append(
            dict(
                row,
                before=before[start:start + 3],
                after=after[start:start + 3],
            )
        )
    expected_changed = (
        sum(1 for row in rows if row["before"] != targets)
        if mode else 0
    )
    expected_after = targets if mode else None
    if (
        error
        or rollback_error
        or not rows
        or completed != len(rows)
        or changed != expected_changed
        or any(row["after"] != (expected_after or row["before"]) for row in rows)
    ):
        raise ValueError(
            "Hero attribute batch incomplete: "
            f"error={error}, rollback_error={rollback_error}, "
            f"changed={changed}, completed={completed}, heroes={len(rows)}"
        )
    return dict(
        rows=rows,
        changed=changed,
        skipped=selection["count"] - len(rows),
        selection_count=selection["count"],
        target=targets if mode else None,
        mode="set" if mode else "query",
    )
