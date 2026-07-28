# Warcraft III 24-Unit Selection Acceptance

Status: active

The final implementation must modify or add Warcraft III-related files so that
the feature activates automatically when the game is started by clicking Play
in the Battle.net UI.

The final implementation must not require:

- manual DLL injection;
- a PID-specific runner;
- a per-launch external patch command;
- launching `Warcraft III.exe` directly for acceptance testing;
- modifying the existing trainer or key-remapping tools.

Completion still requires:

- full 24-unit selection and control groups;
- working orders for units 13-24: move, attack, point target, unit target,
  abilities, and Shift queues;
- native subgroup selection and automatic caster arbitration;
- a 4x6 portrait layout;
- stable operation without crashes.

Do not mark the persistent goal complete until every item above passes a fresh
normal-launch live test.
