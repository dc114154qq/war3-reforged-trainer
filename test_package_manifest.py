from pathlib import Path


def test_frozen_package_requests_admin_for_cross_integrity_game_access():
    spec = (Path(__file__).parent / "War3ReforgedTrainer-2.0.3.spec").read_text(encoding="utf-8")
    assert "uac_admin=True" in spec
    assert "uac_admin=False" not in spec
