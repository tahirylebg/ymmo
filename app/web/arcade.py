"""Hairline drawing of the brand arcade, in true perspective (used by the `arches()` macro).

The arcade is modelled in 3D (a wall pierced by round arches, with thickness, voussoirs and an
entablement), seen obliquely so that it recedes towards a vanishing point on the right, then
projected with a pinhole camera into an SVG viewBox. A low sun behind the wall casts its shadow
on the ground in front, drawn as a very light flat tint with the arch openings left as light.

Everything is computed once per bay count (lru_cache): the template only prints path strings.
"""

from __future__ import annotations

import math
from functools import lru_cache

VIEW_W, VIEW_H = 1200, 560

# Arcade proportions (metres, roughly those of the 3D hero scene).
BAY = 3.4
PIER = 0.78
RADIUS = (BAY - PIER) / 2
SPRING = 2.9
WALL_TOP = 5.0
DEPTH = 0.9
VOUSSOIR = 0.34
ENTABLATURE = 0.62

# Viewer: eye height, wall start, recession angle (from the line of sight, towards the right).
EYE = 2.0
START = (-7.5, 11.0)  # (x, z) of the first pier, in front of and left of the viewer
ANGLE = math.radians(62)
# Sun behind the wall: (towards the viewer, along the wall, down); a short shadow.
SUN = (1.0, 0.3, -1.2)

Point3 = tuple[float, float, float]


def _frame():
    along = (math.sin(ANGLE), 0.0, math.cos(ANGLE))  # direction in which the arcade recedes
    toward_viewer = (math.cos(ANGLE), 0.0, -math.sin(ANGLE))  # wall normal, viewer side
    return along, toward_viewer


def _wall_point(t: float, y: float, inset: float = 0.0) -> Point3:
    """Point on the wall: `t` along the arcade, `y` above ground, `inset` into its thickness."""
    along, normal = _frame()
    return (
        START[0] + t * along[0] - inset * normal[0],
        y - EYE,
        START[1] + t * along[2] - inset * normal[2],
    )


def _arch_outline(t_center: float, radius: float, inset: float, steps: int = 18) -> list[Point3]:
    """Half circle of an arch (springing left to springing right) in the wall plane."""
    return [
        _wall_point(t_center - radius * math.cos(a), SPRING + radius * math.sin(a), inset)
        for a in (math.pi * i / steps for i in range(steps + 1))
    ]


def _opening(t_center: float, inset: float) -> list[Point3]:
    """Full outline of an opening: up the left jamb, over the arch, down the right jamb."""
    return [
        _wall_point(t_center - RADIUS, 0, inset),
        *_arch_outline(t_center, RADIUS, inset),
        _wall_point(t_center + RADIUS, 0, inset),
    ]


def _shadow_of(point: Point3) -> Point3:
    """Where the sun ray through `point` meets the ground (y = -EYE)."""
    along, normal = _frame()
    toward, side, down = SUN
    ray = (
        toward * normal[0] + side * along[0],
        down,
        toward * normal[2] + side * along[2],
    )
    height = point[1] + EYE
    s = height / -ray[1]
    return (point[0] + s * ray[0], -EYE, point[2] + s * ray[2])


def _project(point: Point3) -> tuple[float, float]:
    x, y, z = point
    return x / z, -y / z


@lru_cache(maxsize=16)
def arcade_paths(count: int = 5) -> dict[str, str]:
    """SVG path data for an arcade of `count` bays: keys main, reveal, voussoirs, shadow."""
    count = max(1, min(int(count), 9))
    length = count * BAY
    centers = [(i + 0.5) * BAY for i in range(count)]

    main: list[list[Point3]] = []
    reveal: list[list[Point3]] = []
    voussoirs: list[list[Point3]] = []

    for c in centers:
        main.append(_opening(c, 0))                       # front edge of the opening
        reveal.append(_arch_outline(c, RADIUS, DEPTH))    # back edge: shows the wall thickness
        reveal.append([_wall_point(c - RADIUS, 0, DEPTH), _wall_point(c - RADIUS, SPRING, DEPTH)])
        main.append(_arch_outline(c, RADIUS + VOUSSOIR, 0, 20)[2:-2])  # extrados
        for k in (2, 4, 6, 8, 10):                        # a few joints, keystone in the middle
            a = math.pi * k / 12
            r_out = RADIUS + VOUSSOIR * (1.35 if k == 6 else 1)
            voussoirs.append([
                _wall_point(c - RADIUS * math.cos(a), SPRING + RADIUS * math.sin(a)),
                _wall_point(c - r_out * math.cos(a), SPRING + r_out * math.sin(a)),
            ])

    # Wall ends, ground line, entablement (architrave and cornice) along the whole arcade.
    main.append([_wall_point(0, 0), _wall_point(0, WALL_TOP + ENTABLATURE)])
    main.append([_wall_point(0, 0, DEPTH), _wall_point(0, WALL_TOP + ENTABLATURE, DEPTH)])
    top = WALL_TOP + ENTABLATURE
    main.append([_wall_point(0, 0), _wall_point(length, 0)])
    main.append([_wall_point(0, WALL_TOP), _wall_point(length, WALL_TOP)])
    main.append([_wall_point(0, top), _wall_point(length, top)])
    reveal.append([_wall_point(0, top, DEPTH), _wall_point(length, top, DEPTH)])
    reveal.append([_wall_point(0, top), _wall_point(0, top, DEPTH)])

    # Cast shadow: the wall silhouette on the ground, the openings let the light through.
    silhouette = [
        _wall_point(0, 0), _wall_point(length, 0),
        _shadow_of(_wall_point(length, top)),
        _shadow_of(_wall_point(0, top)),
    ]
    shadow = [silhouette] + [[_shadow_of(p) for p in _opening(c, 0)] for c in centers]

    # Fit everything into the viewBox: ground of the nearest pier on the bottom edge.
    projected = [_project(p) for poly in main + reveal + shadow for p in poly]
    min_x = min(p[0] for p in projected)
    max_x = max(p[0] for p in projected)
    min_y = min(p[1] for p in projected)
    max_y = max(p[1] for p in projected)
    scale = min(VIEW_W / (max_x - min_x), VIEW_H / (max_y - min_y))
    offset_x = (VIEW_W - (max_x - min_x) * scale) / 2 - min_x * scale
    offset_y = VIEW_H - max_y * scale

    def path(polys: list[list[Point3]], close: bool = False) -> str:
        end = "Z" if close else ""
        return "".join(
            "M" + "L".join(
                f"{x * scale + offset_x:.0f} {y * scale + offset_y:.0f}"
                for x, y in (_project(p) for p in poly)
            ) + end
            for poly in polys
        )

    return {
        "main": path(main),
        "reveal": path(reveal),
        "voussoirs": path(voussoirs),
        "shadow": path(shadow, close=True),
    }
