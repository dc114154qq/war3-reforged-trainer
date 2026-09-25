# Critical damage source correction

Observed code path: the old setter wrote only the `AIxr`/`AIsc` controller.
When absent, it added a controller with zero critical chance and changed its
damage field. The trainer summed that damage field into its display even though
the new controller could not trigger a critical hit. This explains how a 500%
readback could coexist with attacks that still appeared to use another source's
150% multiplier; the combat explanation remains a hypothesis until tested.

Current behavior: damage readout is the highest multiplier among recognized
sources with nonzero trigger chance. Damage writes update every such source,
preserve each chance, verify every instance and aggregate, and restore all
attempted writes on failure. No source means no write, rather than a hidden
zero-chance ability. Critical chance and unrelated stat setters retain their
existing paths. The GUI labels the value as a highest multiplier, not a sum.

Verification:
- C fixture covers two active providers, one inactive provider, no active
  provider, spell-critical providers, injected write failure, failed rollback,
  non-finite input, and pre-existing single-source/chance-creation behavior.
- Relevant regression: 70 passed, 1 known localization test deselected.
- Full suite before the last localization-only edit: 2460 passed, 17 skipped,
  1 failed. The failed English-display coverage test had 84 untranslated
  trainer literals at HEAD; an AST comparison found one new untranslated literal.
  That new literal is now translated; unrelated legacy strings remain.
- Isolated production bridge build passed x64 ABI validation. Read-only live
  selected-unit query on PID 22708 returned 226 fields, critical and spell
  critical chances 100%, highest damage 150% for both, with no warnings.

Not verified: combat damage after a 500% write, cross-map persistence, unknown
custom critical sources outside the recognized ability IDs, external-machine
hook installation, talent icon visuals, and native game drag-and-drop into any
equipment slot. The last of these remains a separate product gap: the existing
any-slot toggle controls trainer-directed equip operations, not game UI rules.
