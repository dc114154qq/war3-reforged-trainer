from pathlib import Path


def test_frozen_package_does_not_force_high_integrity_for_medium_game_hook():
    spec = (Path(__file__).parent / "War3ReforgedTrainer-2.0.3.spec").read_text(encoding="utf-8")
    assert "uac_admin=False" in spec
    assert "uac_admin=True" not in spec
