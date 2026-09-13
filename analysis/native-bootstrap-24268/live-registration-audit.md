# 3.0 live native registration bridge — 2026-09-13

The helper source previously refreshed the fixed 2.0.4.23745 profile before
every command. That would overwrite any 3.0 handler addresses supplied by the
new registration operation. `run_command` now detects a batch containing
`WAR3_NATIVE_OP_PERSISTENT_REGISTER_NATIVE` and skips that legacy refresh for
the batch. Other commands retain the old refresh path.

`War3Trainer.register_live_3_native_handlers` accepts only `LiveNativeEntry`
records from the verified 3.0 native table. It maps names to the existing
helper ABI indexes and submits only operation 130 entries. It does not invoke a
handler or mark the whole native feature set ready; later operation support
still needs ABI and game validation.

The separate helper build is `tools/war3_native_helper.3.0-live.dll`, built
from the modified source with clang. SHA256:
`23fd77c54491d7c789e9ee28fc072e775ef2b4394ad65e4d1689998effb41e6d`.
The existing `tools/war3_native_helper.dll` remains untouched. This DLL has not
been loaded into the running game; no native handler was executed.

Validation: the source compiles; the focused suite has **74 tests and 58
subtests passing**, including two registration transaction tests. The next
step is a read-only registration response check using the live 3.0 process,
followed by one carefully bounded ABI probe for a read-only native query.
No gameplay mutation or EXE packaging is claimed here.

## Live registration attempt

On PID 16700, the six names that exist in the helper ABI were submitted using
their current 3.0 addresses. The command file remained in protocol status `1`
(pending) for the full 10-second timeout. No handler ran. The result is in
`live-registration-pending.json`.

The helper's `WH_CALLWNDPROC` hook was installed, but the expected 3.0
window-thread message did not reach `War3HookProc`. Repeating the same command
would reproduce the pending state. The old window-message execution entry is
therefore not a valid 3.0 path yet; the next investigation needs a different
verified game-thread entry or a 3.0-supported dispatch mechanism.

As a bounded comparison, the same six-name registration was tried with
`WH_GETMESSAGE` and `PostThreadMessage(WM_NULL)` instead of
`WH_CALLWNDPROC`/`SendMessageTimeout`. It also remained pending for five
seconds. This rules out the original send-vs-post mismatch as the explanation;
both message-hook entry variants are currently nonfunctional on this 3.0
process. The Python wait path now supports the post mode for future diagnostics,
but the product default remains the original send mode until a working entry is
found.
