from __future__ import annotations

from PySide6.QtCore import QPointF

from slideannotator.annotations.database import AnnotationDB
from slideannotator.annotations.models import AnnotationStore
from slideannotator.utils.geometry import (
    connected_components,
    path_to_rings,
    region_path,
    split_outer_holes,
)

SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
BIG = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
INNER = [(40.0, 40.0), (60.0, 40.0), (60.0, 60.0), (40.0, 60.0)]


def test_region_path_ring_roundtrip(qapp):
    path = region_path(SQUARE)
    rings = path_to_rings(path)
    assert len(rings) == 1
    assert len(rings[0]) == 4


def test_subtraction_makes_a_hole(qapp):
    outer_path = region_path(BIG)
    hole = region_path(INNER)
    result = outer_path.subtracted(hole)
    rings = path_to_rings(result)
    assert len(rings) == 2
    points, holes = split_outer_holes(rings)
    assert len(holes) == 1
    # The hole center must be empty in the even-odd path built from the split rings.
    cut = region_path(points, holes)
    assert not cut.contains(QPointF(50.0, 50.0))
    assert cut.contains(QPointF(5.0, 5.0))


def test_connected_components_groups_touching(qapp):
    a = region_path(SQUARE)
    b = region_path([(5.0, 5.0), (15.0, 5.0), (15.0, 15.0), (5.0, 15.0)])  # overlaps a
    c = region_path([(200.0, 200.0), (210.0, 200.0), (210.0, 210.0), (200.0, 210.0)])  # far
    comps = connected_components([a, b, c])
    sizes = sorted(len(g) for g in comps)
    assert sizes == [1, 2]


def test_merge_regions_undo_redo(qapp):
    store = AnnotationStore()
    a = store.add_region(SQUARE, "CD8")
    b = store.add_region([(5.0, 5.0), (15.0, 5.0), (15.0, 15.0), (5.0, 15.0)], "CD8")
    merged = region_path(a.points).united(region_path(b.points))
    outer, holes = split_outer_holes(path_to_rings(merged))
    store.merge_regions(
        [
            {
                "remove_ids": [a.id, b.id],
                "points": outer,
                "holes": holes,
                "channel": "CD8",
                "color": (10, 20, 30),
            }
        ]
    )
    assert len(store.regions) == 1
    assert next(iter(store.regions.values())).color == (10, 20, 30)
    store.undo()
    assert len(store.regions) == 2
    assert store.get_region(a.id) is not None
    store.redo()
    assert len(store.regions) == 1


def test_apply_region_holes_undo_redo(qapp):
    store = AnnotationStore()
    r = store.add_region(BIG, "CD8")
    result = region_path(r.points).subtracted(region_path(INNER))
    outer, holes = split_outer_holes(path_to_rings(result))
    store.apply_region_holes([(r.id, outer, holes)])
    assert len(store.get_region(r.id).holes) == 1
    store.undo()
    assert len(store.get_region(r.id).holes) == 0
    store.redo()
    assert len(store.get_region(r.id).holes) == 1


def test_db_roundtrip_holes(qapp, tmp_path):
    db = AnnotationDB(tmp_path / "ann.db")
    store = AnnotationStore()
    store.add_region(BIG, "CD8", holes=[INNER])
    db.save_all(store, "slide1")

    loaded = AnnotationStore()
    db.load_for_slide("slide1", loaded)
    region = next(iter(loaded.regions.values()))
    assert len(region.points) == 4
    assert len(region.holes) == 1
    assert len(region.holes[0]) == 4
    db.close()
