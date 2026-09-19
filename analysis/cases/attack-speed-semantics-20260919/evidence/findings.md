# Warcraft III attack-speed field semantics

Date: 2026-09-19

## Verified observations

E1: The trainer labels `attack1_interval` as `Attack 1 interval/cooldown`, maps the
legacy CLI name `attack_speed` to it, and reads/writes `attack_data + 0x200`.
Evidence: `war3_reforged_trainer.py` (`CLI_UNIT_FIELD_KEYS` and
`_append_attack_fields`).

E2: In the captured 2.0.4.23745 runtime, `BlzGetUnitAttackCooldown` calls the
internal getter at RVA `0x682e50`. Weapon 0 is read from
`attack_data + 0x200`; therefore the trainer's old field is the game's weapon
base cooldown, not the final agility-adjusted attack period.
Evidence: `analysis/native-bootstrap-20260907/module-text.bin` and native
registration RVA `0xc5a8b0`.

E3: In 2.0.4.23745, agility changes take a different path. The agility setter
updates the attack component through RVAs `0x6addd0 -> 0x6b10b0 -> 0x680d60`.
The current attack-speed factor is aggregated by RVA `0x682b40`; the effective
timing path combines the weapon cooldown with that factor through the floating
point division routine at RVA `0x30daa0`.
Evidence: the same captured runtime text.

E4: The current 3.0.0.24268 game-thread probe copied the registered runtime code
after validating the PE profile and callback thread. `BlzGetUnitAttackCooldown`
loads the attack component from `unit + 0x760`, then its internal getter at RVA
`0x509980` reads weapon 0 from `attack_data + 0x228` (weapon 1 uses the next
16-byte slot). The current trainer still reads `attack_data + 0x200`, so its
3.0 `attack1_interval` field is not the authoritative native cooldown field.
Evidence: `native-handlers-24268.json` and `runtime-functions-24268.json`.

E5: In 3.0.0.24268, the attack-speed aggregate at RVA `0x509670` starts with
`attack_data + 0x2b8`, conditionally combines `attack_data + 0x2d0`, and clamps
the result to `[0.2, 5.0]`. The effective interval helper at RVA `0x5099a0`
passes the weapon base cooldown and aggregate factor to the floating division
routine at RVA `0x1840d0`. The verified engine relationship is therefore:

`effective attack interval = weapon base cooldown / current attack-speed factor`

`attacks per second = current attack-speed factor / weapon base cooldown`

## Interpretation

Changing agility changes the speed-factor branch, so gameplay attack frequency
changes while the weapon base cooldown remains unchanged. This exactly explains
the report that agility makes attacks faster but the trainer's attack interval
does not move.

The existing label conflates three different values:

1. Weapon base cooldown (BAT/base interval).
2. Current total attack-speed factor from agility, items, abilities, auras and
   slows, after engine limits.
3. Effective attack interval after applying that factor.

For 2.0 the displayed field is item 1. For the current 3.0 source it is also
using a stale offset, so it is not a reliable representation of item 1 there.

## Required product semantics

The field list should expose separate read-only values for base cooldown,
current engine speed factor, effective interval, and attacks per second. The
editable command should be named `base attack cooldown`, not `attack speed`.

Cross-map loss should be detected by snapshotting effective interval and speed
factor before transition and comparing both after the new unit instance is
created. Restoring only the old base cooldown cannot identify whether agility,
an item ability, an aura, or a campaign-specific permanent bonus was lost.

The exact per-agility contribution should be reported from the live engine/map
state rather than hard-coded. Standard Warcraft data commonly corresponds to a
0.02 factor per agility point, but custom maps can alter related constants and
stack additional sources; that assumption is not sufficient for a correction
feature.

## Scope

This investigation was read-only. It copied protected runtime code on the
verified game thread and read component values; it did not write hero stats,
cooldowns, speed factors, or combat state. Product code was not changed.
