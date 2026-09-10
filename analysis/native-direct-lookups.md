# Direct native lookups — app 1.0.19 / game 2.0.4.23745

The basic vital/position writer now asks the native table only for its deduplicated
setter list instead of querying the whole Elephant function set. Whole-selection
movement calls the native-table API directly without an unused external process
memory context or redundant explicit initialization. The lookup API initializes
the persistent table itself. Its underlying implementation already used the DLL;
this removes unnecessary work rather than claiming a new heap-scan elimination.

The guarded setter commands, before/after targeted snapshots and game-thread
whole-selection movement command are unchanged. No helper rebuild or protocol
change is required (protocol 65). The previous source passed 1443 tests and 113
subtests. Focused verification after this Python-only change passed 83 tests and
21 subtests in 5.09 seconds across basic writes, large-number rereads, runtime
features, native group movement and regeneration. Tests reject the old lookup
path, prove only requested setters are queried, and reject external memory access
for group movement. An initially misplaced test assertion was corrected before
the successful run. Accepted EXEs are retained; this code is pending consolidated
gameplay verification with the inventory and transform changes.
