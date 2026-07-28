from types import SimpleNamespace

import pytest

import war3_reforged_trainer as trainer


def test_game_ready_probe_uses_only_local_player_query():
    instance = object.__new__(trainer.War3Trainer)

    class Memory:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    memory = Memory()
    handlers = {
        name: trainer.NativeHandler(name, index, 0x140001000 + index)
        for index, name in enumerate(
            ("GetLocalPlayer", "GetPlayerId", "GetPlayerState"),
            start=1,
        )
    }
    captured = []

    instance._process_memory = lambda: memory
    instance._discover_native_handlers = lambda pm, names: (
        handlers
        if pm is memory and tuple(names) == tuple(handlers)
        else (_ for _ in ()).throw(AssertionError("unexpected readiness discovery"))
    )

    def run_ops(handle, operations):
        captured.append((handle, tuple(operations)))
        return [
            SimpleNamespace(result=value)
            for value in (7, 500, 300, 12, 50)
        ]

    instance._run_native_helper_ops = run_ops

    assert instance.probe_game_ready() == 7
    assert captured == [
        (
            0,
            (
                (
                    trainer.War3Trainer.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_QUERY,
                    0xFFFFFFFF,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["GetPlayerId"].handler_address,
                    handlers["GetPlayerState"].handler_address,
                ),
                (
                    trainer.War3Trainer.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_QUERY,
                    1,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["GetPlayerId"].handler_address,
                    handlers["GetPlayerState"].handler_address,
                ),
                (
                    trainer.War3Trainer.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_QUERY,
                    2,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["GetPlayerId"].handler_address,
                    handlers["GetPlayerState"].handler_address,
                ),
                (
                    trainer.War3Trainer.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_QUERY,
                    5,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["GetPlayerId"].handler_address,
                    handlers["GetPlayerState"].handler_address,
                ),
                (
                    trainer.War3Trainer.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_QUERY,
                    4,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["GetPlayerId"].handler_address,
                    handlers["GetPlayerState"].handler_address,
                ),
            ),
        )
    ]


def test_failed_readiness_probe_is_discarded_before_next_attempt(monkeypatch):
    created = []

    class Candidate:
        def __init__(self):
            created.append(self)

        def probe_game_ready(self):
            if len(created) == 1:
                raise RuntimeError("game map not ready")
            return 3

    monkeypatch.setattr(trainer, "War3Trainer", Candidate)

    with pytest.raises(RuntimeError, match="game map not ready"):
        trainer.create_ready_war3_session()

    session, player_id = trainer.create_ready_war3_session()

    assert session is created[1]
    assert session is not created[0]
    assert player_id == 3
