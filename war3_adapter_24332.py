"""3.0.1.24332 state decoding; other providers retain the shared algorithms."""
from war3_adapter_modules import ComponentAdapter


class ComponentAdapter24332(ComponentAdapter):
    _UNREADABLE_CODE_CHECKS = frozenset(("resolver", "game_state", "context"))

    def frame_context_timeout_ms(self) -> int:
        # This build intermittently retires the externally sampled frame for
        # longer than the historical 250 ms window. Wait before dispatch;
        # never replay a native callback or reuse a retired frame.
        return 1000

    def allows_unreadable_code_check(self, name: str, error: BaseException) -> bool:
        # 3.0.1.24332 maps these image sections as PAGE_NOACCESS while the
        # code is executable. ReadProcessMemory returns ERROR_PARTIAL_COPY
        # (299) for them. PE identity plus live registry/player invariants
        # still validate the selected adapter and object graph.
        return (
            name in self._UNREADABLE_CODE_CHECKS
            and int(getattr(error, "winerror", 0) or 0) == 299
        )

    def decode_game_state(self, encoded):
        d = self.profile.section("decoder")
        mask = 0xFFFFFFFFFFFFFFFF
        value = (encoded + d["add1"]) & mask
        value = ((value << d["rol"]) | (value >> (64 - d["rol"]))) & mask
        value ^= d["xor"]
        value = ((value >> d["ror"]) | (value << (64 - d["ror"]))) & mask
        return (value + d["add2"]) & mask
