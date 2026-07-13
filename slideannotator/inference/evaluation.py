"""Metrics for evaluating an ONNX model against stored annotations.

The functions here are deliberately pure (numpy / plain Python) so they can be
unit-tested without a Qt event loop or an ONNX runtime.  Two evaluation tasks
are supported:

* **Object detection** — predicted boxes are matched to ground-truth boxes via
  greedy IoU matching, producing precision / recall / F1 per marker.
* **Semantic segmentation** — predicted masks are compared to ground-truth
  masks producing mean Dice and mean pixel accuracy per marker.  This path is
  coded but inactive until a segmentation model is configured (``seg_model`` in
  settings.yaml).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# (x1, y1, x2, y2) in scene-pixel coordinates.
Box = tuple[float, float, float, float]

DEFAULT_IOU_THRESHOLD = 0.3


# ---------------------------------------------------------------------------
# Object detection
# ---------------------------------------------------------------------------
def iou(a: Box, b: Box) -> float:
    """Intersection-over-union of two axis-aligned boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0.0 else 0.0


def match_boxes(
    gt: list[Box], pred: list[Box], iou_threshold: float = DEFAULT_IOU_THRESHOLD
) -> tuple[int, int, int]:
    """Greedy IoU matching between ground-truth and predicted boxes.

    Each prediction matches at most one ground-truth box (and vice-versa),
    highest-IoU pairs first.  Returns ``(tp, fp, fn)``.
    """
    n_gt = len(gt)
    n_pred = len(pred)
    if n_gt == 0:
        return 0, n_pred, 0
    if n_pred == 0:
        return 0, 0, n_gt

    # All candidate pairs above threshold, sorted by descending IoU.
    pairs: list[tuple[float, int, int]] = []
    for pi, p in enumerate(pred):
        for gi, g in enumerate(gt):
            v = iou(p, g)
            if v >= iou_threshold:
                pairs.append((v, pi, gi))
    pairs.sort(reverse=True)

    matched_pred: set[int] = set()
    matched_gt: set[int] = set()
    for _v, pi, gi in pairs:
        if pi in matched_pred or gi in matched_gt:
            continue
        matched_pred.add(pi)
        matched_gt.add(gi)

    tp = len(matched_gt)
    fp = n_pred - len(matched_pred)
    fn = n_gt - len(matched_gt)
    return tp, fp, fn


def precision_recall_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Return ``(precision, recall, f1)`` from a confusion count."""
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    denom = precision + recall
    f1 = 2.0 * precision * recall / denom if denom else 0.0
    return precision, recall, f1


# ---------------------------------------------------------------------------
# Semantic segmentation
# ---------------------------------------------------------------------------
def dice_score(gt_mask: np.ndarray, pred_mask: np.ndarray) -> float:
    """Dice coefficient of two boolean masks. Two empty masks score 1.0."""
    gt = np.asarray(gt_mask).astype(bool)
    pred = np.asarray(pred_mask).astype(bool)
    total = int(gt.sum()) + int(pred.sum())
    if total == 0:
        return 1.0
    inter = int(np.logical_and(gt, pred).sum())
    return 2.0 * inter / total


def pixel_accuracy(gt_mask: np.ndarray, pred_mask: np.ndarray) -> float:
    """Fraction of pixels where the two boolean masks agree."""
    gt = np.asarray(gt_mask).astype(bool)
    pred = np.asarray(pred_mask).astype(bool)
    if gt.size == 0:
        return 1.0
    return float((gt == pred).mean())


# ---------------------------------------------------------------------------
# Result aggregation
# ---------------------------------------------------------------------------
@dataclass
class MarkerDetectionResult:
    """Accumulated detection counts for a single marker."""

    marker: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    n_fovs: int = 0

    def add(self, tp: int, fp: int, fn: int) -> None:
        self.tp += tp
        self.fp += fp
        self.fn += fn
        self.n_fovs += 1

    @property
    def precision(self) -> float:
        return precision_recall_f1(self.tp, self.fp, self.fn)[0]

    @property
    def recall(self) -> float:
        return precision_recall_f1(self.tp, self.fp, self.fn)[1]

    @property
    def f1(self) -> float:
        return precision_recall_f1(self.tp, self.fp, self.fn)[2]


@dataclass
class MarkerSegmentationResult:
    """Accumulated segmentation scores for a single marker."""

    marker: str
    dice_scores: list[float] = field(default_factory=list)
    accuracy_scores: list[float] = field(default_factory=list)

    def add(self, dice: float, accuracy: float) -> None:
        self.dice_scores.append(dice)
        self.accuracy_scores.append(accuracy)

    @property
    def n_fovs(self) -> int:
        return len(self.dice_scores)

    @property
    def mean_dice(self) -> float:
        return float(np.mean(self.dice_scores)) if self.dice_scores else 0.0

    @property
    def mean_accuracy(self) -> float:
        return float(np.mean(self.accuracy_scores)) if self.accuracy_scores else 0.0


@dataclass
class EvaluationResult:
    """Full evaluation outcome handed to the results dialog."""

    task: str  # "detection" | "segmentation"
    iou_threshold: float
    n_slides: int
    images: list[str] = field(default_factory=list)
    detection: dict[str, MarkerDetectionResult] = field(default_factory=dict)
    segmentation: dict[str, MarkerSegmentationResult] = field(default_factory=dict)
    skipped_slides: list[str] = field(default_factory=list)

    @property
    def markers(self) -> list[str]:
        """All markers evaluated (excluding the overall aggregate)."""
        keys = self.segmentation if self.task == "segmentation" else self.detection
        return sorted(keys)

    # -- detection helpers ------------------------------------------------
    def detection_result_for(self, marker: str) -> MarkerDetectionResult:
        return self.detection.setdefault(marker, MarkerDetectionResult(marker))

    def overall_detection(self) -> tuple[int, int, int]:
        tp = sum(r.tp for r in self.detection.values())
        fp = sum(r.fp for r in self.detection.values())
        fn = sum(r.fn for r in self.detection.values())
        return tp, fp, fn

    # -- segmentation helpers --------------------------------------------
    def segmentation_result_for(self, marker: str) -> MarkerSegmentationResult:
        return self.segmentation.setdefault(marker, MarkerSegmentationResult(marker))

    def overall_segmentation(self) -> tuple[float, float]:
        dice = [d for r in self.segmentation.values() for d in r.dice_scores]
        acc = [a for r in self.segmentation.values() for a in r.accuracy_scores]
        mean_dice = float(np.mean(dice)) if dice else 0.0
        mean_acc = float(np.mean(acc)) if acc else 0.0
        return mean_dice, mean_acc

    @property
    def total_fovs(self) -> int:
        if self.task == "segmentation":
            return sum(r.n_fovs for r in self.segmentation.values())
        return sum(r.n_fovs for r in self.detection.values())
