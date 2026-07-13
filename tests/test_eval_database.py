from __future__ import annotations

from slideannotator.annotations.eval_database import EvaluationDB
from slideannotator.inference.evaluation import EvaluationResult


def _detection_result() -> EvaluationResult:
    result = EvaluationResult(
        task="detection", iou_threshold=0.3, n_slides=2, images=["slideA", "slideB"]
    )
    result.detection_result_for("CD8").add(8, 2, 0)
    result.detection_result_for("CD68").add(4, 0, 1)
    return result


def test_save_and_read_detection(tmp_path) -> None:
    db = EvaluationDB(tmp_path / "evaluations.db")
    try:
        db.save_evaluation(_detection_result(), "my_model")
        records = db.get_evaluations()
    finally:
        db.close()

    assert len(records) == 1
    rec = records[0]
    assert rec.model_name == "my_model"
    assert rec.model_type == "detection"
    assert rec.iou_threshold == 0.3
    assert rec.n_slides == 2
    assert rec.images == ["slideA", "slideB"]
    assert rec.markers == ["CD68", "CD8"]

    cd8 = rec.marker_metric("CD8")
    assert cd8 is not None
    assert (cd8.tp, cd8.fp, cd8.fn) == (8, 2, 0)

    overall = rec.overall()
    assert overall is not None
    assert (overall.tp, overall.fp, overall.fn) == (12, 2, 1)
    assert rec.n_fovs == 2  # one FOV per marker


def test_segmentation_stores_dice_and_accuracy(tmp_path) -> None:
    result = EvaluationResult(task="segmentation", iou_threshold=0.3, n_slides=1, images=["slideA"])
    result.segmentation_result_for("CD8").add(0.8, 0.9)
    result.segmentation_result_for("CD8").add(0.6, 0.7)

    db = EvaluationDB(tmp_path / "evaluations.db")
    try:
        db.save_evaluation(result, "seg_model")
        records = db.get_evaluations()
    finally:
        db.close()

    rec = records[0]
    assert rec.model_type == "segmentation"
    assert rec.iou_threshold is None
    cd8 = rec.marker_metric("CD8")
    assert cd8 is not None
    assert cd8.mean_dice == 0.7
    assert cd8.n_fovs == 2


def test_multiple_evaluations_sorted_newest_first(tmp_path) -> None:
    db = EvaluationDB(tmp_path / "evaluations.db")
    try:
        first = _detection_result()
        first.images = ["only_one"]
        db.save_evaluation(first, "my_model")
        db.save_evaluation(_detection_result(), "my_model")
        records = db.get_evaluations()
    finally:
        db.close()

    # Two evaluations for the same model.
    assert len(records) == 2
    # Both share the model; newest (all images) first by created_at DESC / id DESC.
    assert records[0].images == ["slideA", "slideB"]
    assert records[1].images == ["only_one"]
