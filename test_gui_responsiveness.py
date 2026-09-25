from pathlib import Path

import war3_reforged_trainer as trainer


def test_initial_game_connection_runs_off_the_tk_event_thread():
    source = Path(trainer.__file__).read_text(encoding="utf-8")
    start = source.index("    def finish_initial_connect(")
    end = source.index("    root.after(100, init)", start)
    startup = source[start:end]

    assert 'state["initial_connect_busy"] = True' in startup
    assert 'start_operation_thread(worker, "war3-initial-connect")' in startup
    assert "with operation_lock:" in startup
    assert 'root.after(0, finish_initial_connect, message, None)' in startup
