from __future__ import annotations

import numpy as np
import onnxruntime as ort

from .nms import _normalize_grid, non_maximum_suppression
from .stardist_utils import polygons_to_label

# Map user-facing device strings to ONNX Runtime execution providers.
# Each list is ordered by preference; ORT picks the first available one.
_PROVIDERS: dict[str, list[str]] = {
    "cpu": ["CPUExecutionProvider"],
    "cuda": ["CUDAExecutionProvider", "CPUExecutionProvider"],
    "tensorrt": ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
    "coreml": ["CoreMLExecutionProvider", "CPUExecutionProvider"],
    "mps": ["CoreMLExecutionProvider", "CPUExecutionProvider"],
    "directml": ["DmlExecutionProvider", "CPUExecutionProvider"],
    "rocm": ["ROCMExecutionProvider", "CPUExecutionProvider"],
}

# The model outputs at half the input resolution (256 vs 512).
# Grid matches the output stride so NMS scales points to full-resolution coords.
_OUTPUT_SCALE = 2
_GRID = _normalize_grid((_OUTPUT_SCALE, _OUTPUT_SCALE), 2)


class StarDistONNX:
    """StarDist instance-segmentation inference via ONNX Runtime.

    The model expects single-channel 512×512 images (NHWC float32) and
    produces a probability map and 32-ray distance map at 256×256.

    Args:
        model_path: Path to the ``.onnx`` model file.
        device: Execution device — one of ``"CPU"``, ``"CUDA"``, ``"MPS"``,
            ``"CoreML"``, ``"TensorRT"``, ``"DirectML"``, ``"ROCm"``.
            Falls back to CPU if the requested provider is unavailable.
        norm_pmin: Lower percentile for input normalisation (default 1).
        norm_pmax: Upper percentile for input normalisation (default 99.8).
    """

    def __init__(
        self,
        model_path: str,
        device: str = "CPU",
        norm_pmin: float = 1.0,
        norm_pmax: float = 99.8,
    ) -> None:
        providers = _PROVIDERS.get(device.lower(), ["CPUExecutionProvider"])
        self.session = ort.InferenceSession(model_path, providers=providers)
        self._input_name: str = self.session.get_inputs()[0].name
        self.norm_pmin = norm_pmin
        self.norm_pmax = norm_pmax

    # ------------------------------------------------------------------
    # Preprocessing
    # ------------------------------------------------------------------

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """Normalise and reshape a single-channel image for inference.

        Args:
            image: 2-D array ``(H, W)``, any numeric dtype.

        Returns:
            Float32 array ``[1, H, W, 1]`` with values clipped to ``[0, 1]``.
        """
        lo, hi = np.percentile(image, [self.norm_pmin, self.norm_pmax])
        img = (image.astype(np.float64) - lo) / (hi - lo + 1e-8)
        img = np.clip(img, 0.0, 1.0).astype(np.float32)
        return img[np.newaxis, :, :, np.newaxis]  # [1, H, W, 1]

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def run(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Run a forward pass on a preprocessed input tensor.

        Args:
            x: Float32 array ``[1, H, W, 1]`` produced by :meth:`preprocess`.

        Returns:
            ``(prob, dist)`` where:

            * ``prob`` — ``[1, H/2, W/2, 1]`` probability map in ``[0, 1]``.
            * ``dist`` — ``[1, H/2, W/2, 32]`` ray-distance map in
              full-resolution pixel units.
        """
        prob, dist = self.session.run(None, {self._input_name: x})
        return prob, dist

    # ------------------------------------------------------------------
    # Postprocessing
    # ------------------------------------------------------------------

    def postprocess(
        self,
        prob: np.ndarray,
        dist: np.ndarray,
        prob_thresh: float = 0.5,
        nms_thresh: float = 0.3,
    ) -> np.ndarray:
        """Convert raw model outputs to an instance label image.

        Steps:

        1. Threshold ``prob`` to collect candidate centroids.
        2. Sort candidates by score (highest first).
        3. Apply NMS via the StarDist C extension (bbox pre-filter + k-d tree).
           Overlap is measured as ``Ainter / min(A1, A2)`` — more robust than
           IoU for objects of very different sizes.
        4. Rasterise accepted polygons into an integer label image.

        Args:
            prob: ``[1, H, W, 1]`` probability map.
            dist: ``[1, H, W, 32]`` ray-distance map (full-resolution units).
            prob_thresh: Minimum score to treat a pixel as a candidate centre.
            nms_thresh: Overlap threshold above which a candidate is suppressed.

        Returns:
            Integer array ``(H*2, W*2)``; background = 0, each object has a
            unique positive integer label.
        """
        prob_map = prob[0, :, :, 0]                    # (out_h, out_w)
        dist_map = np.maximum(1e-3, dist[0])           # (out_h, out_w, n_rays)
        out_h, out_w = prob_map.shape
        inp_h, inp_w = out_h * _OUTPUT_SCALE, out_w * _OUTPUT_SCALE

        points, scores, dists = non_maximum_suppression(
            dist_map,
            prob_map,
            grid=_GRID,
            prob_thresh=prob_thresh,
            nms_thresh=nms_thresh,
        )

        if len(points) == 0:
            return np.zeros((inp_h, inp_w), dtype=np.int32)

        return polygons_to_label(dists, points, prob=scores, shape=(inp_h, inp_w))

    # ------------------------------------------------------------------
    # Polygon extraction
    # ------------------------------------------------------------------

    def predict_polygons(
        self,
        image: np.ndarray,
        prob_thresh: float = 0.5,
        nms_thresh: float = 0.4,
    ) -> list[list[tuple[float, float]]]:
        """Run the full pipeline and return polygon vertices instead of a label image.

        Returns:
            List of polygons; each polygon is a list of ``(x, y)`` tuples in
            input-image pixel coordinates.
        """
        x = self.preprocess(image)
        prob, dist = self.run(x)
        prob_map = prob[0, :, :, 0]
        dist_map = np.maximum(1e-3, dist[0])

        points, _scores, dists = non_maximum_suppression(
            dist_map,
            prob_map,
            grid=_GRID,
            prob_thresh=prob_thresh,
            nms_thresh=nms_thresh,
        )
        if len(points) == 0:
            return []

        n_rays = dists.shape[-1]
        angles = np.linspace(0, 2 * np.pi, n_rays, endpoint=False)
        polygons: list[list[tuple[float, float]]] = []
        for pt, d in zip(points, dists):
            # pt = (row, col) = (y, x); distances in full-resolution pixels
            vy = pt[0] + d * np.sin(angles)
            vx = pt[1] + d * np.cos(angles)
            polygons.append(list(zip(vx.tolist(), vy.tolist())))
        return polygons

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def __call__(
        self,
        image: np.ndarray,
        prob_thresh: float = 0.5,
        nms_thresh: float = 0.4,
    ) -> np.ndarray:
        """Run the full preprocessing → inference → postprocessing pipeline.

        Args:
            image: 2-D single-channel array ``(512, 512)``, any numeric dtype.
            prob_thresh: Probability threshold for candidate selection.
            nms_thresh: Overlap threshold for non-maximum suppression.

        Returns:
            Integer label image ``(512, 512)``; 0 = background.
        """
        x = self.preprocess(image)
        prob, dist = self.run(x)
        return self.postprocess(prob, dist, prob_thresh=prob_thresh, nms_thresh=nms_thresh)
