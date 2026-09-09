# Buff callback migration, protocol 54

Offline audit of the pinned 2.0.4.23745 image and captured runtime text found
the buffer constructor at RVA 0x5b5660, extent 369 bytes (PE exception table).
Its stores match the 0x24-byte War3BuffData layout: duration at 0x18, hero
duration at 0x1c, addon at 0x20. The constructor signature used by the previous
Python discovery occurs 42 times in the runtime text, including operands of
unrelated instructions; it is not a sufficient function identity.

The function at RVA 0x91cc20 (715 bytes) calls that constructor at 0x91ce0c
with the stack buffer in RCX, ability object in RDX and zero in R8D. At
0x91ce3c it fetches vtable slot 0xa00; at 0x91ce67 it calls that pointer with
ability/target/buffer/duration in RCX/RDX/R8/R9. Other functions that reference
the same constructor use slot 0xa00 with different arguments, so the offset
alone must not determine the ABI. The "roar_effect" name in the fixture is a
working identification from this implementation; actual ANht mapping still
requires checking in the game.

`tools/audit_buff_contract.py` verifies image and text SHA256, exception-table
extents, complete instruction decoding, the relevant argument setup and calls,
and exact agreement with `native-buff-contract-23745.json`. The audit ran
successfully against the local image and saved runtime text. No live reads or
mutations were required.

Op 157 now accepts mode 5 for the buff path. It validates the exact effect and
constructor bodies using the profile and resolves the constructor in the DLL.
Construction is followed by fresh ability/unit identity and callback checks
before applying the buff. The existing guarded creation/removal transaction
surrounds this operation. The Python roar entry delegates to it; external
vtable reads, rel32 discovery and old ability creation/cleanup were removed
from this entry. Rawcode is still passed to the engine resource lookup; the
ABI gate applies to effect classes, not a requirement for a template unit.

Evidence is deliberately separated:

- The recorded real code establishes constructor layout and the calling
  convention at one specific effect implementation. Full-body runtime guards
  reject mutated code, wrong function addresses and nonexecutable regions.
- Isolated invocation tests use fake constructor/buff functions to check the
  four arguments, duration bounds, exceptions, and unit/ability/callback/level
  changes during construction. They do not execute the captured constructor
  against actual Warcraft objects.
- Existing C dispatcher lifecycle tests cover unknown buff ABI refusal and
  temporary-ability cleanup. The Python entry test forbids external memory
  discovery. Initial combined buff/direct suite: 51 tests passed (4.70 s).

Full regression: **877 tests and 103 subtests passed** (49.09 s), recorded in
`analysis/native-buff-regression.log`. Rebuilt DLL SHA256:
`bfe717a96b70ba8794f23e5908849b2bff891312a13669e0a7c6a4956138c5da`.

Limitations: game mapping of ANht and other desired resources to the verified
effect implementation is not yet established. Other buff classes are refused
until their ABI is verified; full-map enumeration and toggle paths remain to
be migrated. Application version is 1.0.19. No application EXE was built and
no user gameplay acceptance is claimed. The overall goal remains unfinished.
