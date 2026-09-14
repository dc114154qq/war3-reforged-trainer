# Native hook variant experiment — 2026-09-14

- Temporarily tested replacing native executor thread hooks with WH_GETMESSAGE.
- Static regression passed: 24 tests.
- No improvement was observed: the trainer session was already circuit-broken as native unavailable, and no game handler/write was invoked.
- The experiment was reverted; product remains on the previously verified WH_CALLWNDPROC transport.
