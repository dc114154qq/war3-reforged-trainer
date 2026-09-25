# Optional native unit fields after bridge failure

The external 2.0.6 read stack reaches `_unit_stats_for_candidate_24268` while
building the indexed selected-unit field table. Hook installation fails before
the attribute query runs. Previously that exception discarded the whole table.

The 2.0.7 reader now keeps independently read basic fields after a cleaned-up
bridge failure. It omits unverified 3.0 armor, defense type, intelligence, and
stat-details values, shows a read-only unavailable row, and writes a diagnostic
log retaining the original engine report. A bridge failure with retained
allocations or quarantine still aborts the read. No failing native query is
reported as a successful attribute read.

Automated evidence: 181 focused tests passed, including indexed base fields,
hero intelligence omission, verified native armor retention, and unsafe-cleanup
propagation. This does not repair the external hook-install failure itself or
prove full functionality on an affected machine; a current-build external log
is still required for that conclusion.
