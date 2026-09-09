# Strength/agility field semantics: offline evidence

2026-09-09; branch `codex/v1.0.19-hero-stat-audit`.
User accepted the named gameplay points for 047b4e5, but reported strength and
agility reading slightly below the requested values. The following notes package
b93ee58 documented that observation; it did not change the setter behavior.

## Verified mismatch

The field display reads `GetHeroStr(unit, false)` / `GetHeroAgi(unit, false)`.
The corresponding component-field write changes only hero data +0x108 / +0x130.
Its immediate readback verifies those stored bytes, not the getter result.

In the captured 2.0.4.23745 executable:

- GetHeroStr at RVA 0xc50800 delegates to 0x116eb40; GetHeroAgi at 0xc504f0
  delegates to 0x116e140.
- Both internal queries compute an additional term using hero data +0xd0 and
  +0x188 (strength) / +0x1a8 (agility), then add the stored +0x108 / +0x130.
- When the boolean argument is false, both queries call 0x1173140 and subtract
  another result. The true path skips that subtraction.
- Thus the displayed base query has the form `stored + calculated - excluded`.
  Writing `stored = target` does not establish `query(false) = target`.
  This audit does not assign an exact gameplay source or sign to the two terms.
- SetHeroStr at 0xc9bc20 and SetHeroAgi at 0xc9b8e0 delegate to 0x116f880 and
  0x116f440. These calculate the current base query value, subtract it from the
  requested target and pass the difference to component adjustment routines
  0x6adf10 / 0x6addd0.
- Those routines add the difference to the component fields and call further
  update routines. The agility path visits attack (+0x5c0) and movement (+0x5b0)
  components; the strength path includes a call to 0x115e630. The direct store
  bypasses these calls; their complete gameplay effects are not claimed here.

This proves the current component setter is not semantically equivalent to the
displayed game query or official setter. It supplies a concrete correction
direction without guessing offsets, scanning units or adding delays. It does
not prove which term caused this particular user's small downward difference.

## Reproduction

`tools/audit_hero_stat_contract.py` hashes the on-disk image and saved runtime
text against the pinned capture, obtains function boundaries from PE exception
metadata, decodes all ten functions and checks 25 key instructions. It emits
full function bytes, hashes and disassembly for review.

Command from this workspace:

```powershell
python tools/audit_hero_stat_contract.py --image 'D:/Warcraft III/_retail_/x86_64/Warcraft III.exe' --text analysis/native-bootstrap-20260907/module-text.bin --output analysis/native-hero-stat-contract.json
```

Result: `Verified 10 functions and 25 instructions`.
Evidence is in `analysis/native-hero-stat-contract.json`.

## Next implementation requirement

Route editable base strength/agility through their official native setters in
one game-thread transaction, bound to both unit and hero-component generation;
read the same base query used by the display before reporting success. Validate
identity across callbacks and preserve batch efficiency. Do not treat a raw
component readback as proof that the requested displayed stat was achieved.

No trainer/DLL behavior changed in this audit. Both delivered EXEs are intact;
no game process was read or modified. This is offline reverse-engineering
evidence, not another round of user acceptance or a fix already delivered.
