# In-map resource fallback — 2026-09-14

- User confirmed the client had entered the map before this test.
- PID 38352 remained the explicit target.
- Native bootstrap returned timeout status 1; the operation was not retried indefinitely.
- The trainer marked native unavailable for this session and fell back to the verified 3.0 indexed-property route.
- Read-only local resource result: gold 997469, lumber 999839, food 38/72.
- Read-only resource-group result: 28 groups, including player slots 0 through 27.
- Selected-unit read in the same map session: 15 selected units, HP 650/650, MP 255/255, position 316.515/384.097.
- Static regression: 10 passed.
- No memory writes, native mutations, cloning, ability, item, or elephant operations were executed.
