# Preserve item identity across mixed field writes

2026-09-09; branch `codex/v1.0.19-property-identity`; application 1.0.19.
Native protocol 56 and DLL unchanged.

## Reproduced defect

`_write_unit_fields_to_candidate` batches basic values first, regardless of input
order. It previously replaced its local candidate with the basic setter's fresh
readback. If the inventory changed between the original field snapshot and that
readback, a later quantity or item replacement setter received the new inventory
identity. Its otherwise correct item guard therefore checked the replacement,
not the item belonging to the original request.

Eight new quantity tests failed against the prior implementation (expected
identity rejection did not occur). They exercised both input orders and changes
to item JASS handle, address, rawcode and full generation separately. Native
responses were injected; this reproduces controller behavior without modifying
the running game. It does not establish that a particular map trigger causes it.

## Fix and verification

The basic readback is retained separately for returned HP/MP/position values.
Subsequent field setters retain the original candidate and inventory identity.
Their existing targeted native refresh now rejects changed items before any
item mutation is submitted. No extra game callbacks or sleeps were added.

Coverage expanded to 16 rejection cases across quantity/item replacement and
two successful unchanged-item cases. Successful tests check request result order,
actual HP readback, item quantity result and full identity in submitted commands.

- Targeted regression: 51 passed, 3 subtests passed.
- Full regression: 960 passed, 105 subtests passed in 48.54 seconds.
- Log: `analysis/native-mixed-write-binding-regression.log`.
- Whitespace/diff checks passed.

This is code-level verification, not recent user gameplay acceptance. No EXE
was packaged. Existing effect experiments remain intact.

Mixed requests still execute in stages; if an item changes after a successful
basic write, the request raises while the earlier basic write remains applied.
This fix prevents retargeting; it does not claim atomic rollback across fields.
