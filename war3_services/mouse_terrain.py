"""Bounded intersection of a camera ray and the game's terrain height field.

The target plane only defines the ray. A landing point must independently
satisfy the terrain equation; a small change between iterates is insufficient.
No process addresses, game versions or execution routes belong here.
"""
from __future__ import annotations

import math
from collections.abc import Callable


def intersect_mouse_terrain(
    eye: tuple[float, float, float],
    plane_point: tuple[float, float],
    plane_z: float,
    height_at: Callable[[float, float], float],
    *,
    diagnostics: dict | None = None,
) -> tuple[float, float]:
    """Use safeguarded secant steps, with at most 16 terrain queries.

    Parameter t=0 is the eye and t=1 is the initial plane intersection.
    Vertical residual, horizontal plane correction and the local secant's
    remaining horizontal step must be <=0.05 world units. Flat terrain takes
    one or two queries; linear slopes normally
    take three. A discontinuity or failed query never becomes a guessed point.
    """
    report = diagnostics if diagnostics is not None else {}
    report.update(method="bounded_ray_terrain_secant_v1", tolerance=0.05,
                  query_limit=16, samples=[], converged=False)

    def fail(reason):
        report["failure"] = reason
        error = RuntimeError("鼠标落点尚未确认，本次未执行传送：" + reason)
        error.report = {"mouse_projection": report}
        raise error

    origin = tuple(map(float, eye))
    initial = (float(plane_point[0]), float(plane_point[1]), float(plane_z))
    if len(origin) != 3 or not all(
        math.isfinite(value) and abs(value) <= 1_000_000.0
        for value in (*origin, *initial)
    ):
        fail("相机射线坐标无效")
    delta = tuple(initial[index] - origin[index] for index in range(3))
    if abs(delta[2]) <= 1e-9:
        fail("相机射线与地形高度平面平行")
    horizontal_length = math.hypot(delta[0], delta[1])
    horizontal_per_height = horizontal_length / abs(delta[2])
    # Restrict every point on the ray, rather than clamping individual secant
    # coordinates off the ray. The map's existing edge margin is applied later.
    limit = min(
        ((1_000_000.0 if step > 0 else -1_000_000.0) - start) / step
        for start, step in zip(origin, delta) if step
    )
    if not math.isfinite(limit) or limit < 1.0:
        fail("相机射线超出有效世界范围")
    samples = []
    t = 1.0
    for iteration in range(16):
        point = tuple(start + step * t for start, step in zip(origin, delta))
        row = dict(t=t, x=point[0], y=point[1], ray_z=point[2])
        report["samples"].append(row)
        report["query_count"] = len(report["samples"])
        terrain_z = float(height_at(point[0], point[1]))
        if not math.isfinite(terrain_z) or abs(terrain_z) > 1_000_000.0:
            fail("地形高度读回无效")
        residual = point[2] - terrain_z
        horizontal_error = abs(residual) * horizontal_per_height
        remaining_step = math.inf
        if residual == 0:
            remaining_step = 0.0
        elif samples:
            previous_t, previous_residual = samples[-1]
            difference = residual - previous_residual
            if difference:
                remaining_step = abs(residual * (t - previous_t) / difference) * horizontal_length
        row.update(terrain_z=terrain_z, height_residual=residual,
                   horizontal_residual=horizontal_error,
                   remaining_horizontal_step=remaining_step if math.isfinite(remaining_step) else None)
        if abs(residual) <= 0.05 and horizontal_error <= 0.05 and remaining_step <= 0.05:
            report.update(converged=True, point=point[:2], terrain_z=terrain_z,
                          query_count=len(report["samples"]))
            return point[0], point[1]
        samples.append((t, residual))
        if len(samples) == 1:
            proposed = (terrain_z - origin[2]) / delta[2]
        else:
            brackets = [(first, second) for first in samples for second in samples
                        if first[0] < second[0] and (first[1] < 0) != (second[1] < 0)]
            if brackets:
                (a, fa), (b, fb) = min(brackets, key=lambda pair: pair[1][0] - pair[0][0])
            else:
                (a, fa), (b, fb) = samples[-2:]
            denominator = fb - fa
            if abs(denominator) > 1e-12 * max(1.0, abs(fa), abs(fb)):
                proposed = b - fb * (b - a) / denominator
            else:
                proposed = t * (2.0 if b >= a else 0.5)
            if brackets and (not a + (b - a) * 0.02 < proposed < b - (b - a) * 0.02
                             or iteration % 4 == 3):
                proposed = (a + b) * 0.5
        if not math.isfinite(proposed):
            fail("地形求交产生无效坐标")
        if proposed <= 0:
            proposed = t * 0.5
        elif proposed > limit:
            proposed = (t + limit) * 0.5
        if any(abs(proposed - previous_t) <= 1e-12 * max(1.0, abs(proposed))
               for previous_t, _ in samples):
            fail("地形求交未收敛")
        t = proposed
    fail("地形求交超过采样上限")
