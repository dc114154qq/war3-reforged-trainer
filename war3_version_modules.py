"""Compiled layout approval registry; data packs cannot approve new code semantics."""
OLD_BUILD=(0x8664,1789189744,236277760)
PTR_BUILD=(0x8664,1790661601,236408832)
NAMES=('legacy_layout','talents','talent_icons','equipment','stat_details','direct_effect')
IMPLEMENTATIONS={name+'_24268_v1':(name,frozenset({OLD_BUILD})) for name in NAMES}
# The PTR keeps the 3.0 native ABI and extension object semantics.  The
# individual addresses/layouts live in its GameProfile; this registry only
# approves the compiled implementation against the exact PE fingerprint.
IMPLEMENTATIONS.update({
    name+'_24323_v1': (name, frozenset({PTR_BUILD})) for name in NAMES
})


def validate_implementation(name,implementation,fingerprint):
    record=IMPLEMENTATIONS.get(implementation)
    return bool(record and record[0]==name and tuple(fingerprint) in record[1])


def known_implementation(name,implementation):
    record=IMPLEMENTATIONS.get(implementation)
    return bool(record and record[0]==name)
