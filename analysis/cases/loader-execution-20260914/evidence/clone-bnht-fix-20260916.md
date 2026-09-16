# Clone BNht Fix — 2026-09-16

## Observed

- User-provided diagnostic for PID `32020` reported `error=66`, `completed=0/1`, `changed=0` while cloning a minion.
- The saved clone work row decoded from the diagnostic result had source rawcode `fdtg` and reserved rawcode `BNht`.

## Verified cause

- Warcraft III 3.0 exposes `BNht` through the unit ability enumerator, but it is an engine buff component and is not addable with the unit ability API.
- The bridge now skips all `Bxxx` rawcodes in the addable-ability pass while retaining item-side ability filtering and normal ability copying.

## Verification

- Clone fixture regression: `37 passed`.
- Full 3.0 product suite: `493 passed`.
- Live PID `32020`: one selected unit cloned with `changed=1`, `ability_count=23`, and `item_count=5`.
- Frozen r4 self-test: `ok=true`, `frozen=true`, `retired_helper_present=false`.
- EXE: `dist-2.0.1-test-3.0.0.24268-r4/War3ReforgedTrainer-v2.0.1-test.exe`.
- EXE SHA256: `88557D98E354943647C7021125614C43297EAF2C5C823D041D7B144D30E958C0`.
