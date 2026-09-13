# 3.0 loader gate dispatch follow-up

The current loader `.text` capture shows the two patched entry targets are
state-machine wrappers rather than ordinary callable APIs:

- `loader+0x1351be0` preserves `rcx/rdx/r8`, validates a mixed state value,
  then enters internal dispatch through `0x56c0e0` and `0x0e2330`.
- `loader+0x1da6be0` preserves the stack guard and `r8`, validates a second
  state value, then enters `0x1e852f0` and `0x10df3b0`.

The internal functions themselves are heavily flattened/opaque: branch state is
derived from mutable loader globals and several call targets are reached through
computed branches. Direct external calls are not a valid way to reproduce the
thread context. The entry wrappers also have no normal internal call site; the
loader/system thread trampoline jumps into them.

This evidence explains the earlier helper result: a window hook can serialize a
command but does not place execution inside the loader's gated callback context.
The next useful artifact is a read-only trace of the actual game thread while
one of these gate wrappers runs, with the callback target and context slot
captured. No gate, thread start, callback, or protection state was modified in
this follow-up.
