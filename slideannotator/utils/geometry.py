from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainterPath, QPolygonF

Point = tuple[float, float]
Ring = list[Point]


def region_path(points: list[Point], holes: list[Ring] | None = None) -> QPainterPath:
    """Build an even-odd QPainterPath from an outer ring plus optional hole rings.

    Even-odd fill decides filled-vs-empty by nesting depth, so rings nested inside
    another render as holes automatically regardless of winding order.
    """
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    for ring in [points, *(holes or [])]:
        if len(ring) < 3:
            continue
        poly = QPolygonF([QPointF(x, y) for x, y in ring])
        path.addPolygon(poly)
        path.closeSubpath()
    return path


def path_to_rings(path: QPainterPath) -> list[Ring]:
    """Decompose a path into point-list rings (closing duplicate dropped, len >= 3)."""
    rings: list[Ring] = []
    for poly in path.toSubpathPolygons():
        pts = [(p.x(), p.y()) for p in poly]
        if len(pts) >= 2 and pts[0] == pts[-1]:
            pts = pts[:-1]
        if len(pts) >= 3:
            rings.append(pts)
    return rings


def _signed_area(ring: Ring) -> float:
    area = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def split_outer_holes(rings: list[Ring]) -> tuple[Ring, list[Ring]]:
    """Split rings into (outer, holes): the largest-area ring is the outer boundary."""
    if not rings:
        return [], []
    outer_idx = max(range(len(rings)), key=lambda i: abs(_signed_area(rings[i])))
    outer = rings[outer_idx]
    holes = [r for i, r in enumerate(rings) if i != outer_idx]
    return outer, holes


def connected_components(paths: list[QPainterPath]) -> list[list[int]]:
    """Group path indices into connected components where two paths intersect (touch/overlap)."""
    n = len(paths)
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if paths[i].intersects(paths[j]):
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())
