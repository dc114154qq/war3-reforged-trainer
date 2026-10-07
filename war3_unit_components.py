"""Compatibility entry points; component layouts belong to the selected adapter."""
from war3_game_profile import current_profile


def _adapter(registry):
    profile = getattr(registry, "profile", None) or current_profile()
    return profile.adapter.components


def read_unit_component_nodes(memory, registry, owner):
    return _adapter(registry).nodes(memory, registry, owner)


def read_unit_components(memory, registry, owner, names):
    return _adapter(registry).components(memory, registry, owner, names)
