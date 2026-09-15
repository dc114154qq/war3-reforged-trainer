import math
from unittest.mock import Mock

import pytest

import war3_reforged_trainer as product


def snapshot(screen=(32767, 32767)):
    return {
        "target": (100.0, 200.0, 50.0),
        "eye": (100.0, 0.0, 250.0),
        "fields": (0.0, 5000.0, 5.3, math.radians(70.0), 0.0, math.pi / 2.0, 0.0, 0.0),
        "screen": screen,
    }


def test_camera_projection_hits_target_plane_at_center():
    x, y = product.War3Trainer._mouse_world_from_camera_24268(snapshot(), 1706, 960)
    assert x == pytest.approx(100.0, abs=0.2)
    assert y == pytest.approx(200.0, abs=0.2)


def test_camera_projection_accepts_dpi_scaled_render_coordinates():
    x, y = product.War3Trainer._mouse_world_from_camera_24268(
        snapshot(screen=(1280, 720)), 1706, 960, 1.5,
    )
    assert x == pytest.approx(100.0, abs=0.2)
    assert y == pytest.approx(200.0, abs=0.2)


def test_current_mouse_route_uses_camera_snapshot_not_retired_world_helper():
    trainer = object.__new__(product.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer.hwnd = 123
    trainer.camera_snapshot_24268 = Mock(return_value=snapshot())
    trainer._client_size_24268 = Mock(return_value=(1706, 960))
    trainer._screen_scale_24268 = Mock(return_value=1.0)
    trainer.mouse_world_point_24268 = Mock(side_effect=AssertionError("retired world helper"))
    x, y = trainer.query_mouse_world_position()
    assert (x, y) == pytest.approx((100.0, 200.0), abs=0.1)
    trainer.camera_snapshot_24268.assert_called_once_with()
