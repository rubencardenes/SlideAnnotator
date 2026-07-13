from __future__ import annotations

import numpy as np
import pytest

from slideannotator.inference.evaluation import (
    EvaluationResult,
    dice_score,
    iou,
    match_boxes,
    pixel_accuracy,
    precision_recall_f1,
)


def test_iou_identical_boxes() -> None:
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0


def test_iou_disjoint_boxes() -> None:
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0


def test_iou_partial_overlap() -> None:
    # Half-overlap: intersection 50, union 150 -> 1/3.
    assert iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(50 / 150)


def test_match_boxes_all_match() -> None:
    gt = [(0, 0, 10, 10), (20, 20, 30, 30)]
    pred = [(0, 0, 10, 10), (20, 20, 30, 30)]
    tp, fp, fn = match_boxes(gt, pred, iou_threshold=0.3)
    assert (tp, fp, fn) == (2, 0, 0)


def test_match_boxes_false_positive_and_negative() -> None:
    gt = [(0, 0, 10, 10), (100, 100, 110, 110)]
    pred = [(0, 0, 10, 10), (50, 50, 60, 60)]
    tp, fp, fn = match_boxes(gt, pred, iou_threshold=0.3)
    assert (tp, fp, fn) == (1, 1, 1)


def test_match_boxes_below_threshold_is_not_a_match() -> None:
    gt = [(0, 0, 10, 10)]
    pred = [(8, 0, 18, 10)]  # IoU = 2/18 ~ 0.11
    tp, fp, fn = match_boxes(gt, pred, iou_threshold=0.3)
    assert (tp, fp, fn) == (0, 1, 1)


def test_match_boxes_one_prediction_matches_only_one_gt() -> None:
    gt = [(0, 0, 10, 10), (0, 0, 10, 10)]  # two identical GT boxes
    pred = [(0, 0, 10, 10)]  # a single prediction
    tp, fp, fn = match_boxes(gt, pred, iou_threshold=0.3)
    assert (tp, fp, fn) == (1, 0, 1)


def test_match_boxes_empty_inputs() -> None:
    assert match_boxes([], [(0, 0, 1, 1)]) == (0, 1, 0)
    assert match_boxes([(0, 0, 1, 1)], []) == (0, 0, 1)
    assert match_boxes([], []) == (0, 0, 0)


def test_precision_recall_f1() -> None:
    p, r, f1 = precision_recall_f1(tp=8, fp=2, fn=2)
    assert p == pytest.approx(0.8)
    assert r == pytest.approx(0.8)
    assert f1 == pytest.approx(0.8)


def test_precision_recall_f1_no_predictions() -> None:
    assert precision_recall_f1(0, 0, 5) == (0.0, 0.0, 0.0)


def test_dice_score() -> None:
    gt = np.zeros((4, 4), dtype=np.uint8)
    pred = np.zeros((4, 4), dtype=np.uint8)
    gt[:2, :] = 1
    pred[1:3, :] = 1
    # intersection = 4, sizes 8 + 8 -> 2*4/16 = 0.5
    assert dice_score(gt, pred) == pytest.approx(0.5)


def test_dice_score_both_empty_is_one() -> None:
    z = np.zeros((3, 3), dtype=np.uint8)
    assert dice_score(z, z) == 1.0


def test_pixel_accuracy() -> None:
    gt = np.array([[1, 0], [1, 0]], dtype=np.uint8)
    pred = np.array([[1, 0], [0, 0]], dtype=np.uint8)
    assert pixel_accuracy(gt, pred) == pytest.approx(0.75)


def test_evaluation_result_detection_aggregation() -> None:
    result = EvaluationResult(task="detection", iou_threshold=0.3, n_slides=2)
    result.detection_result_for("CD8").add(5, 1, 1)
    result.detection_result_for("CD8").add(3, 0, 2)
    result.detection_result_for("CD68").add(4, 4, 0)

    cd8 = result.detection["CD8"]
    assert (cd8.tp, cd8.fp, cd8.fn, cd8.n_fovs) == (8, 1, 3, 2)
    assert result.overall_detection() == (12, 5, 3)
    assert result.total_fovs == 3
