"""Bundled algorithms and original build evidence; packs cannot introduce code."""
OLD_BUILD=(0x8664,1789189744,236277760)
PTR_BUILD=(0x8664,1790661601,236408832)
NAMES=('legacy_layout','talents','talent_icons','equipment','stat_details','direct_effect')
IMPLEMENTATIONS={name+'_24268_v1':(name,frozenset({OLD_BUILD})) for name in NAMES}
# The PTR keeps the 3.0 native ABI and extension object semantics.  The
# individual addresses/layouts live in its GameProfile; this registry only
# records its original evidence. Instruction patches still require an exact
# fingerprint; data-driven parsers can be reused by an explicitly adapted pack.
IMPLEMENTATIONS.update({
    name+'_24323_v1': (name, frozenset({PTR_BUILD})) for name in NAMES
})
IMPLEMENTATIONS["legacy_layout_24332_v1"] = (
    "legacy_layout", frozenset({(0x8664, 1791134929, 236732416)})
)


def validate_implementation(name,implementation,fingerprint):
    record=IMPLEMENTATIONS.get(implementation)
    return bool(record and record[0]==name and tuple(fingerprint) in record[1])


def known_implementation(name,implementation):
    record=IMPLEMENTATIONS.get(implementation)
    return bool(record and record[0]==name)


def resolve_implementation(profile, name):
    """Bind approved bundled code, never import names from a data pack."""
    profile.require_module(name)
    from war3_adapter_modules import IMPLEMENTATION_PROVIDERS
    implementation = profile.data["modules"][name]["implementation"]
    return IMPLEMENTATION_PROVIDERS[implementation](profile)
