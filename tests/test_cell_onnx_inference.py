from __future__ import annotations

import numpy as np
import pytest

from slideannotator.inference.CellONNXInference import (
    CellONNXInfer,
    CellONNXInferDFINE,
    nms,
)


def test_cell_onnx_infer_preprocess_shape() -> None:
    infer = CellONNXInfer(model_path=None, device="cpu")
    image = np.random.randint(0, 255, size=(512, 512, 3)).astype(np.float32)

    output = infer.preprocess(image)

    assert output.shape == (1, 3, 512, 512)
    assert output.dtype == np.float32


def test_cell_onnx_infer_preprocess_rejects_wrong_ndim() -> None:
    infer = CellONNXInfer(model_path=None, device="cpu")
    image = np.zeros((512, 512), dtype=np.float32)

    with pytest.raises(ValueError):
        infer.preprocess(image)


def test_cell_onnx_infer_postprocess_filters_by_threshold() -> None:
    infer = CellONNXInfer(model_path=None, device="cpu")
    # shape (1, N, 5): x1, y1, x2, y2, score
    detections = np.array(
        [
            [
                [0, 0, 10, 10, 0.9],
                [0, 0, 5, 5, 0.1],
                [1, 1, 2, 2, 0.6],
                [1, 1, 2, 2, 0.05],
                [1, 1, 2, 2, 0.7],
                [1, 1, 2, 2, 0.02],
            ]
        ],
        dtype=np.float32,
    )

    kept = infer.postprocess([detections], prob_thresh=0.5)

    assert kept.shape == (3, 5)
    assert sorted(kept[:, 4].tolist()) == pytest.approx([0.6, 0.7, 0.9])


def test_cell_onnx_infer_dfine_preprocess_scales_to_unit_range() -> None:
    infer = CellONNXInferDFINE(model_path=None, device="cpu", tile_size=64)
    image = np.full((64, 64, 3), 65535, dtype=np.uint16)

    output = infer.preprocess(image, tile_size=64)

    assert output.shape == (1, 3, 64, 64)
    assert np.allclose(output, 1.0)


def test_nms_removes_overlapping_boxes() -> None:
    boxes = np.array(
        [
            [0, 0, 10, 10],
            [1, 1, 11, 11],  # heavily overlaps with the box above
            [50, 50, 60, 60],  # separate box
        ],
        dtype=np.float32,
    )
    scores = np.array([0.9, 0.8, 0.7], dtype=np.float32)

    keep = nms(boxes, scores, iou_threshold=0.5)

    assert keep == [0, 2]
