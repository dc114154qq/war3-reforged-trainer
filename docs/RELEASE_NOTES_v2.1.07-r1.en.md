# Warcraft III 3.0 Trainer 2.1.07

Built on the published 2.1.07 source. This update adds detailed backpack and skill diagnostics. The software version remains 2.1.07; this is a replacement build.

- Record the selected unit, backpack item, complete object identities, six classic inventory slots, and why each component is preserved, repaired or stopped.
- Record each observed native lookup, addition, activation, removal and item ability attachment: function, arguments, stage, return value and subsequent readback. An exception retains the observation that the call was entered but did not return normally.
- Record trainer/game builds, bridge hash, actual native registrations and handlers. A registered native function does not establish that a particular ability definition such as AIni was loaded.
- Fullscreen Monsoon and Starfall record each cast, hold, observation, parameter restoration and cleanup. Failures retain the original exception chain.
- Save both readable .log and structured .jsonl files with shared operation IDs and sequence numbers. Persist the dispatch boundary before sending the native request, then save its result after callback return.
- Record success and failure. The native journal holds up to 1,024 calls per execution; overflow is explicitly counted and the final call is retained.

The observers use the existing calls. They perform no additional diagnostic skill additions, game writes, automatic retries or mouse-click collection.

Code verification passed 4,758 tests and 120 subtests, with 29 tests skipped. The targeted suite passed 750 tests. Production bridge compilation and adapter dependency audits passed. The previous fixes, four exact game profiles and external transport corrections remain available. No local game interaction was performed.

The earlier external-machine log confirms that AIni addition was rejected. The final internal rejection cause and the result on that machine remain unverified. Detailed diagnostics do not establish that the external fault has disappeared.

This release belongs to the Warcraft III 3.0 section. Historical versions and the 2.0/community section remain available.
