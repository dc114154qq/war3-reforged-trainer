# Toggle command transaction (protocol 55)

The old toggle entry returned success from a Python set keyed by JASS handle
and rawcode. That did not prove that the same ability still existed or that
the toggle remained on. It also split add, visibility changes and order issue
into separately dispatched calls without a bound unit generation.

The new op 161 carries a unit identity guard, ability rawcode and positive
signed order ID. One game-thread callback captures the ability identity,
creates it from the map resource if missing, makes a helper-owned hidden
ability visible for the order, issues the requested enable order, and restores
its hidden state. Every game callback is followed by identity/level checks.
Preexisting abilities not owned by the helper keep their visibility unchanged.

The DLL's ownership records include full unit and ability generations, wrapper
and data identities. They track who changed visibility, never whether an
effect is enabled. Every request issues an order, including repeated requests.
When that unit/rawcode is encountered with another ability generation, its old
record is discarded without mutating the replacement. If the order fails,
only an ability created by this invocation is eligible for removal. A prior
helper-owned instance is instead rehidden if it still has its exact identity.
An unknown creation outcome or unsafe cleanup is reported separately.

Tests run the production C dispatcher against fake native functions. The 26
toggle tests passed (3.15 s), covering existing/resource-created abilities,
repeated requests, same-handle/rawcode instance replacement, rejected orders,
callback exceptions, changed unit/ability identities, restoring visibility on
a failed repeated request, invalid orders and pointer-free Python routing.

Full regression: **903 tests and 103 subtests passed** (49.57 s), recorded in
`analysis/native-toggle-regression.log`. Rebuilt DLL SHA256:
`0dcfe5b287a79ba81a66109c302470da0ae4cf57876955c3ce08b5ba3e6ab7dc`.
Application version stays 1.0.19. No application EXE was built or game state
changed, and no current user gameplay acceptance is claimed.

Remaining limits: the return value proves engine order acceptance, not a
readback of the ability's internal active bit; actual ANms activation and
mana-dependent deactivation require gameplay checks. Hidden ownership records
are retired when their unit/rawcode is revisited with another generation;
records for never-revisited destroyed units remain allocated until game exit.
Visibility has no independent getter/readback in this path. Failed cleanup
with unproven ownership is not forced. Global direct-effect enumeration still
uses the legacy controller discovery route and remains outstanding.
