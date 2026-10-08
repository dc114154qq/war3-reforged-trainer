"""External-memory vertical slice; preserve proven property validation semantics."""

from war3_game_profile import profile_scope
from war3_game_session import ObjectAddress, OperationEvidence
from war3_capabilities import CapabilitySet


class ExternalMemoryBackend:
    def __init__(self, session):
        self.session = session

    def read_save_codes(self, memory, *, prefix="-load", cancel=None, progress=None):
        """Bounded read-only string scan; no object offsets, native calls or replay state."""
        from war3_save_codes import scan_memory_codes

        self.session.prepare(memory)
        identity, epoch = self.session.identity, self.session.epoch
        result = scan_memory_codes(memory, prefix=prefix, cancel=cancel, progress=progress)
        self.session.prepare(memory)
        if self.session.identity != identity or self.session.epoch != epoch:
            raise RuntimeError("游戏或地图在扫描期间发生变化，本次候选已丢弃，请重新读取。")
        self.session.cache["save_code_scan_diagnostics"] = {
            key: value for key, value in result.items() if key != "codes"
        }
        return result

    def read_player_properties(self, memory, registry, player, player_id):
        from war3_player_resources import read_player_properties

        CapabilitySet(self.session.profile).require("resources")
        return read_player_properties(memory, registry, player, player_id)

    def selected_units(self, memory):
        from war3_classic_selection import read_player_selection

        registry, context, mode = self.session.prepare(memory)
        with profile_scope(self.session.profile):
            player = registry.local_player_for_mode(memory, mode.value)
            snapshot = read_player_selection(memory, player)
            refs = tuple(
                self.session.bind_unit(memory, registry, ObjectAddress(unit))
                for unit in snapshot.units
            )
            if read_player_selection(memory, player) != snapshot:
                raise RuntimeError("Selection changed during identity binding")
            return refs

    def write_basic_fields(self, memory, registry, candidate, requested):
        from war3_basic_fields import write_basic_fields

        self.session.require_write()
        CapabilitySet(self.session.profile).require("basic_fields")
        ref = self.session.bind_unit(
            memory, registry, ObjectAddress(candidate.unit_address)
        )
        if ref.handle.value != candidate.handle:
            raise RuntimeError("Candidate object replaced")
        self.session.resolve(memory, registry, ref)
        try:
            result = write_basic_fields(memory, registry, candidate, requested)
            self.session.resolve(memory, registry, ref)
        except Exception:
            # A failed field batch can be partially applied. Never auto-repeat it.
            self.session.uncertain = True
            self.session.last_evidence = OperationEvidence(uncertain=True)
            raise
        self.session.last_evidence = OperationEvidence(True, True, False, True, False)
        return result
