"""Capabilities are independently checked; matching registration is not ABI proof."""

from dataclasses import dataclass
from war3_game_profile import ProfileError


@dataclass(frozen=True)
class Capability:
    name: str
    available: bool
    missing: tuple[str, ...]


# Modules with instruction/layout semantics remain pinned to a compiled adapter.
MODULES = {
    "direct_cast": ("direct_effect",),
    "extension": ("talents", "equipment"),
    "equipment": ("equipment",),
    "equipment_effect": ("equipment",),
    "item_safety": ("equipment",),
    "equipment_probe": ("equipment",),
    "legacy_equipment_probe": ("equipment",),
    "talent_order": ("talents",),
    "talent_icon_control": ("talent_icons",),
    "stat_details": ("stat_details",),
    "effect": ("direct_effect",),
    "world_effect": ("direct_effect",),
    "basic_fields": ("legacy_layout",),
    "resources": ("legacy_layout",),
    "item_catalog": ("legacy_layout",),
}


class CapabilitySet:
    def __init__(self, profile, entries=None, common=()):
        self.profile = profile
        self.entries = entries or {}
        self.common = tuple(common)

    def check(self, name, signatures=(), request=None):
        missing = list(self.common)
        # Internal attack routines need separately located addresses; a generic
        # native handler table cannot make inherited/unknown RVAs executable.
        if name == "attack_speed" and any(self.profile.section("addresses")[key] == 0
                for key in ("speed_factor", "effective_interval", "unit_resolver")):
            missing.append("Attack timing internals have not been adapted for this build")
        modules = MODULES.get(name, ())
        if name == "extension" and request is not None:
            action = request.get("action", 0)
            modules = (
                ("talents",)
                if action in (7, 10)
                else ("equipment",)
                if action in (2, 4, 9, 11, 12)
                else ()
            )
        for module in modules:
            try:
                self.profile.require_module(module)
            except ProfileError as exc:
                missing.append(str(exc))
        for native, signature in signatures:
            entry = self.entries.get(native)
            if entry is None:
                missing.append("Missing native: " + native)
            elif entry.signature != signature:
                missing.append("Native signature differs: " + native)
        return Capability(name, not missing, tuple(missing))

    def require(self, name, signatures=(), request=None):
        result = self.check(name, signatures, request)
        if not result.available:
            raise ProfileError("; ".join(result.missing))
        return result
