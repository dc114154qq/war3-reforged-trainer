"""Per-profile immutable adapter binding, separate from feature transactions."""
from functools import cached_property


class GameAdapter:
    def __init__(self, profile):
        self.profile = profile

    def provider(self, name):
        from war3_version_modules import resolve_implementation
        return resolve_implementation(self.profile, name)

    @cached_property
    def equipment(self):
        return self.provider("equipment")

    @cached_property
    def components(self):
        return self.provider("legacy_layout")

    @cached_property
    def attack(self):
        return self.components.subprovider("attack")

    @cached_property
    def talents(self):
        return self.provider("talents")

    @cached_property
    def stats(self):
        return self.provider("stat_details")

    @cached_property
    def effects(self):
        return self.provider("direct_effect")

    @cached_property
    def icons(self):
        return self.provider("talent_icons")

    @cached_property
    def properties(self):
        return self.components.subprovider("properties")

    @cached_property
    def items(self):
        return self.components.subprovider("items")

    @cached_property
    def abilities(self):
        return self.components.subprovider("abilities")

    @cached_property
    def units(self):
        return self.components.subprovider("units")

    @cached_property
    def selection(self):
        return self.components.subprovider("selection")

    @cached_property
    def legacy(self):
        return self.components.subprovider("legacy")
