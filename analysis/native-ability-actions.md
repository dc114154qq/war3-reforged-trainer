# Bound ability actions (protocol 49)

Selected-unit add, remove, reset and level operations now share one guarded
native action path. Python sends the unit object, full generation and owner;
the DLL resolves the current JASS handle only from the validated object table,
checks the ability wrapper/data identity before and after every engine callback,
and returns the final level from the same transaction. Batches reserve one
identity guard and at most 15 actions, so a later action cannot continue after
the guard has failed.

The action path supports map-resource ability creation without requiring a
template unit. Reset removes the current instance, verifies absence, then adds
the ability again. Removal-all carries each enumerated ability generation.
Existing ability field operations keep their separate full identity binding.

Validation:

- The production dispatcher fixture covers add/no-op add, remove/no-op remove,
  reset, level set/readback, missing resources, generation and wrapper changes,
  invalid levels, callbacks that return failure or throw, and batch stop behavior.
- UI action tests prohibit legacy native discovery, external process memory and
  fixed waits. A 32-entry bundle is split into 15/15/2 actions with one guard
  per native command.
- Full regression: **748 tests and 103 subtests passed** (36.32 s).
- The optimized helper compiled and live read-only validation on PID 15028
  returned ability metadata for nine units: two heroes with 21/25 abilities and
  seven nonheroes with 7/8 abilities. No add/remove/set/reset was executed.
  See `native-ability-actions-readonly.json`.

Application version remains 1.0.19. The validated EXE is untouched. Gameplay
mutation and new EXE testing remain pending; remaining legacy discovery paths
still require the final reachability audit.
