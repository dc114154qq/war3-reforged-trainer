# Game-thread effect deadlines (protocol 52)

Held effects now include their requested duration in op 159, arg1 (1..120000
milliseconds). The DLL starts a thread timer before any mutation and sets the
deadline after executing the effect. A timer or module-pin failure rejects the
start before creating or modifying an ability. The timer belongs to the same
game thread as the start command and shares its reentrancy guard. There is no
worker-thread game access or blocking sleep in the DLL.

At the deadline, the callback refreshes the exact-build native table, then
attempts the same identity/order/area-checked cleanup as an explicit finish.
It does not need the controller, a command file, or another selection read.
Only due records cause a native-table refresh. When no deadlines remain the
timer is killed. A failed automatic cleanup is attempted once and retained for
explicit retry, not retried on every timer tick.

Successful cleanup saves one of 32 bounded completion receipts with the token,
JASS handle and full unit identity. A delayed or duplicate finish acknowledges
that receipt without another stop, area write or removal. A mismatched unit
cannot use it. Older evicted tokens return not found.

To keep TIMERPROC valid after controller exit and Windows hook removal, the
helper pins its own module on first held effect. That DLL stays loaded until
the game exits, even after all effect records have completed. Development
builds loaded into one running game can therefore retain more than one helper
module; restarting the game releases them. The requested duration remains a
minimum deadline: callback delivery depends on the game thread pumping Windows
messages, so this is not an exact real-time timer guarantee.

Evidence:

- 44 lifecycle tests passed (5.14 s), including deadline/not-yet-due behavior,
  delayed finish, wrong-thread/reentrant callbacks, a recycled ability, and
  inability to create a timer or pin the helper.
- A separate compiled executable uses real SetTimer, GetModuleHandleEx,
  PeekMessage/DispatchMessage and KillTimer. After start it sends no controller
  command until the timer has stopped the effect, restored area and removed
  the temporary ability. Late finish does not repeat those mutations. Engine
  objects and functions in that executable are fake, not Warcraft gameplay.
- Source and tracked DLL use protocol 52; application version remains 1.0.19.
  No game mutation calls or application EXE packaging were performed.

Full regression: **848 tests and 103 subtests passed** (45.27 s), recorded in
`analysis/native-effect-deadline-regression.log`. Rebuilt DLL SHA256:
`cb94a0ad0782c284c48c615b4cb1c956e54038f81d590417bbea6e0e3008e45b`.

Still unproven/incomplete: actual Warcraft timer dispatch during menus,
pauses/map transitions and after controller process death; recovery when
creation/effect execution fails before a deadline can be established; UI
reconciliation of failed records; distinguishing a reissued identical order
from the original order. Identity or external-field conflicts still refuse
cleanup and retain the record. These limitations do not justify declaring the
whole DLL-chain goal complete.
