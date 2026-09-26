"""world operations; transport and lifecycle belong to GameSession."""
from war3_selection_protocol import SIGNATURES

class WorldService:
    def world_batch(self, action, rawcode=0, value=0):
        from war3_world_protocol import SIGNATURES as WORLD_SIGNATURES, build_work as build, decode_work as decode
        if (isinstance(action, bool) or not isinstance(action, int) or action not in range(1, 7)
                or isinstance(rawcode, bool) or not isinstance(rawcode, int) or not 0 <= rawcode <= 0xffffffff
                or isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xffffffff):
            raise ValueError('Invalid current-engine world operation')
        names = tuple(n for n, _ in WORLD_SIGNATURES)
        return self._execute(
            'world', names,
            lambda entries, tls: build(entries, tls, action, rawcode, value),
            decode,
            dict(action=action, rawcode=rawcode, value=value),
        )


    def bulk_batch(self, action, value=0):
        from war3_bulk_protocol import SIGNATURES as BULK_SIGNATURES, build_work as build, decode_work as decode
        if (isinstance(action, bool) or action not in range(1, 6)
                or isinstance(value, bool) or value not in (0, 1)):
            raise ValueError('Invalid current-engine bulk action')
        names = tuple(n for n, _ in SIGNATURES + BULK_SIGNATURES)
        return self._execute(
            'bulk', names,
            lambda entries, tls: build(entries, tls, action, value),
            decode,
            dict(action=action, value=value),
        )


    def mouse_world_point(self):
        from war3_mouse_protocol import SIGNATURES as MOUSE_SIGNATURES, build_work as build, decode_work as decode
        return self._execute(
            'mouse', tuple(n for n, _ in MOUSE_SIGNATURES),
            lambda entries, tls: build(entries, tls),
            decode,
            {},
        )


    def mouse_screen_point(self):
        from war3_screen_protocol import SIGNATURES as SCREEN_SIGNATURES, build_work as build, decode_work as decode
        return self._execute(
            'screen_mouse', tuple(n for n, _ in SCREEN_SIGNATURES),
            lambda entries, tls: build(entries, tls),
            decode,
            {},
        )


    def camera_snapshot(self):
        from war3_camera_protocol import SIGNATURES as CAMERA_SIGNATURES, build_work as build, decode_work as decode
        return self._execute(
            'camera', tuple(n for n, _ in CAMERA_SIGNATURES),
            lambda entries, tls: build(entries, tls),
            decode,
            {},
        )


    def terrain_height(self, x_bits, y_bits):
        from war3_terrain_protocol import SIGNATURES as TERRAIN_SIGNATURES, build_work as build, decode_work as decode
        values = (x_bits, y_bits)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError('Terrain coordinates must be float bit integers')
        return self._execute(
            'terrain', tuple(n for n, _ in TERRAIN_SIGNATURES),
            lambda entries, tls: build(entries, tls, x_bits, y_bits),
            decode,
            dict(x_bits=x_bits, y_bits=y_bits),
        )


    def map_bounds(self):
        from war3_map_bounds_protocol import SIGNATURES as BOUNDS_SIGNATURES, build_work as build, decode_work as decode
        return self._execute(
            'map_bounds', tuple(n for n, _ in BOUNDS_SIGNATURES),
            lambda entries, tls: build(entries, tls), decode, {},
        )
