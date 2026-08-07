import numpy as np
import onnxruntime as ort
from loguru import logger
from PIL import Image

from .ONNXInferenceBase import ONNXInferenceBase, sigmoid


def nms(boxes, scores, iou_threshold):
    # Compute the area of the boxes and sort by score
    x1, y1, x2, y2 = np.split(boxes, 4, axis=1)
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)

        # Compute IoU
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        intersection = w * h
        union = areas[i] + areas[order[1:]] - intersection
        iou = intersection / union

        # Keep boxes with IoU less than the threshold
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]

    return keep


class CellONNXInfer(ONNXInferenceBase):
    def __init__(
        self,
        model_path: str,
        device: str = "gpu",
        depth16: bool = False,
        normalize_scheme: str = "v1",
        mean=None,
        std=None,
    ):
        self.mean, self.stdinv = self.get_normalization_values(mean, std, depth16, normalize_scheme)

        self.model_path = model_path
        self.provider = self._resolve_provider(device)
        if self.model_path is not None:
            self.session = ort.InferenceSession(
                self.model_path,
                providers=[self.provider],
            )

    def _model_forward(self, input_im):
        # run onnx inference
        return self.session.run(None, {"input": input_im})

    def preprocess(self, input: np.array) -> np.array:
        # input is a numpy array of size (512, 512, 3)
        if len(input.shape) != 3:
            logger.info("error input array must have 3 dimensions Y,X,C")
            raise ValueError
        input = input.astype("float32")

        # RGB to BGR
        input[:, :, [0, 2]] = input[:, :, [2, 0]]
        # Normalize
        input = (input - self.mean) * self.stdinv

        # now we add one dimension before and another after and convert to float32
        input = input[np.newaxis, ...].astype("float32")
        input = np.transpose(input, (0, 3, 1, 2))
        return input

    def postprocess(self, results_ort, prob_thresh):
        if results_ort[0].shape[1] > 4:
            return results_ort[0][results_ort[0][:, :, 4] > prob_thresh]
        else:
            return results_ort[0]

    def predict(self, input, prob_thresh=0.5):
        # pre-process image
        input = self.preprocess(input)
        # run inference
        results_ort = self._model_forward(input)
        # post_process obj detection results
        results = self.postprocess(results_ort, prob_thresh)

        return results


class CellONNXInferRTDETR(ONNXInferenceBase):
    def __init__(
        self,
        model_path,
        device: str = "gpu",
        tile_size=512,
        depth16=True,
        normalize_scheme: str = "v2",
        mean=None,
        std=None,
    ):
        self.mean, self.stdinv = self.get_normalization_values(mean, std, depth16, normalize_scheme)

        self.model_path = model_path
        self.provider = self._resolve_provider(device)

        if self.model_path is not None:
            self.session = ort.InferenceSession(
                self.model_path,
                providers=[self.provider],
            )
        self.tile_size = tile_size

    def preprocess(self, input: np.array, tile_size: int = 512) -> np.array:
        # input is a numpy array of size (512, 512, 3)
        if len(input.shape) != 3:
            print("error input must have three dimensions X,Y,C")

        # Pad the image if size is not standard
        if input.shape[1] != tile_size or input.shape[2] != tile_size:
            input, _ = self._pad_img(input, tile_size, (-1, -1))

        # Make sure data is float32
        input = input.astype("float32")

        # now we add one dimension at the beginning (batch dimension)
        input = (input - self.mean) * self.stdinv
        input = input[np.newaxis, ...].astype("float32")
        input = np.transpose(input, (0, 3, 1, 2)).astype("float32")

        return input

    def _model_forward(self, input_im):
        # run onnx inference
        orig_target_sizes = np.array([input_im.shape[2:4]], dtype="int64")
        return self.session.run(None, {"images": input_im, "orig_target_sizes": orig_target_sizes})

    def predict(self, input, prob_thresh=0.5, iou_th=0.5):
        input = self.preprocess(input, self.tile_size)
        # run onnx inference
        results_ort = self._model_forward(input)
        results = self.postprocess(results_ort, prob_thresh, iou_th)
        return results

    def postprocess(self, results_ort, prob_thresh, iou_th):
        boxes = results_ort[1][results_ort[2] > prob_thresh]
        scores = results_ort[2][results_ort[2] > prob_thresh]

        if iou_th > 0:
            keep_indices = nms(boxes, scores, iou_th)

            # Filter the boxes and scores
            boxes = boxes[keep_indices]
            scores = scores[keep_indices]

        # stack scores and bboxes
        scores = scores.reshape(-1, 1)
        boxes = np.hstack((boxes, scores))

        return boxes


class CellONNXInferRFDETR(ONNXInferenceBase):
    """ONNX inference for RF-DETR cell detectors.

    RF-DETR exposes a single fixed-resolution input (e.g. 576x576) and two
    outputs: ``dets`` (normalised cx,cy,w,h boxes in [0, 1]) and ``labels``
    (per-class logits). Source tiles are resized to the model resolution and
    detections are returned in the *source* tile's pixel space, so the output
    contract matches :class:`CellONNXInferDFINE` — ``(N, 5)`` rows of
    ``xmin, ymin, xmax, ymax, score``.

    Normalisation defaults to RF-DETR's standard transform: uint16 tiles are
    scaled to [0, 1] and then ImageNet-normalised. Pass ``normalize_scheme="none"``
    to skip mean/std (0-1 only), or supply explicit ``mean``/``std``.
    """

    def __init__(
        self,
        model_path,
        device: str = "cpu",
        tile_size: int = 512,
        normalize_scheme: str = "imagenet",
        scale: float = 65535.0,
        mean=None,
        std=None,
        session=None,
    ):
        self.model_path = model_path
        self.provider = self._resolve_provider(device)

        self.session = session
        if self.session is None and self.model_path is not None:
            self.session = ort.InferenceSession(
                str(self.model_path),
                providers=[self.provider],
            )

        self.tile_size = tile_size
        self.normalize_scheme = normalize_scheme
        self.scale = scale
        self.mean, self.stdinv = self._rfdetr_norm(normalize_scheme, mean, std)

        # Read the input name and square resolution from the model when available.
        self.input_name = "input"
        self.model_res = 576
        if self.session is not None:
            inp = self.session.get_inputs()[0]
            self.input_name = inp.name
            res = inp.shape[-1]
            if isinstance(res, int) and res > 0:
                self.model_res = res

    @staticmethod
    def _rfdetr_norm(scheme, mean, std):
        """Return ``(mean, stdinv)`` broadcastable over a (3, H, W) tensor, or
        ``(None, None)`` when no mean/std normalisation is applied."""
        if scheme == "none":
            return None, None
        # ImageNet statistics — RF-DETR's default transform.
        mean = np.array(mean if mean is not None else [0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array(std if std is not None else [0.229, 0.224, 0.225], dtype=np.float32)
        return mean.reshape(3, 1, 1), (1.0 / std).reshape(3, 1, 1)

    def preprocess(self, input_img: np.array) -> np.array:
        # input is a numpy array of size (H, W, 3)
        if input_img.ndim != 3:
            logger.info("error input array must have 3 dimensions Y,X,C")
            raise ValueError

        # Resize each channel to the model resolution (float32 bilinear).
        channels = []
        for c in range(3):
            im = Image.fromarray(input_img[:, :, c].astype(np.float32), mode="F")
            im = im.resize((self.model_res, self.model_res), Image.BILINEAR)
            channels.append(np.asarray(im, dtype=np.float32))
        arr = np.stack(channels, axis=0)  # (3, res, res)

        # Scale intensities (16-bit -> [0, 1] by default), then optional mean/std.
        arr = arr / self.scale
        if self.mean is not None:
            arr = (arr - self.mean) * self.stdinv

        return arr[np.newaxis, ...].astype("float32")  # (1, 3, res, res)

    def _model_forward(self, input_im):
        # run onnx inference
        return self.session.run(None, {self.input_name: input_im})

    def postprocess(self, results_ort, prob_thresh, iou_th):
        dets = results_ort[0][0]  # (num_queries, 4) normalised cx,cy,w,h
        logits = results_ort[1][0]  # (num_queries, num_classes)

        # Per-query score = best class probability (sigmoid over logits).
        scores = sigmoid(logits).max(axis=1)
        keep = scores > prob_thresh
        dets = dets[keep]
        scores = scores[keep]

        if dets.shape[0] == 0:
            return np.zeros((0, 5), dtype=np.float32)

        # normalised cx,cy,w,h -> xyxy in source-tile pixel space.
        cx, cy, w, h = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3]
        s = self.tile_size
        boxes = np.stack(
            [(cx - w / 2) * s, (cy - h / 2) * s, (cx + w / 2) * s, (cy + h / 2) * s],
            axis=1,
        )

        if iou_th > 0 and boxes.shape[0] > 1:
            keep_idx = nms(boxes, scores, iou_th)
            boxes = boxes[keep_idx]
            scores = scores[keep_idx]

        return np.hstack((boxes, scores.reshape(-1, 1))).astype(np.float32)

    def predict(self, input, prob_thresh=0.5, iou_th=0.5):
        input = self.preprocess(input)
        # run onnx inference
        results_ort = self._model_forward(input)
        # post_process obj detection results
        return self.postprocess(results_ort, prob_thresh, iou_th)


def create_cell_detector(
    model_path, device: str = "cpu", normalize_scheme: str = "imagenet"
) -> ONNXInferenceBase:
    """Build the cell-detection inference wrapper matching an ONNX model.

    Dispatches on the model's input/output signature so different exported
    detectors work interchangeably from ``settings.cell_det_models``:

      * RF-DETR — a single ``input`` and ``dets`` + ``labels`` outputs.
      * D-FINE / RT-DETR — ``images`` + ``orig_target_sizes`` inputs and
        ``labels`` / ``boxes`` / ``scores`` outputs (the default).

    ``normalize_scheme`` selects the RF-DETR preprocessing normalisation
    (``"imagenet"`` for 0-1 scale + ImageNet mean/std, or ``"none"`` for a
    16-bit 0-1 scale only). It is ignored by D-FINE/RT-DETR, which always
    scale by 65535.

    The inspection session is reused by the chosen wrapper, so the model is
    loaded only once.
    """
    provider = ONNXInferenceBase._resolve_provider(device)
    session = ort.InferenceSession(str(model_path), providers=[provider])
    input_names = [i.name for i in session.get_inputs()]
    output_names = {o.name for o in session.get_outputs()}

    if len(input_names) == 1 and {"dets", "labels"} <= output_names:
        logger.info(f"Detected RF-DETR cell detector (normalize={normalize_scheme}): {model_path}")
        return CellONNXInferRFDETR(
            str(model_path),
            device=device,
            normalize_scheme=normalize_scheme,
            session=session,
        )

    logger.info(f"Detected D-FINE/RT-DETR cell detector: {model_path}")
    return CellONNXInferDFINE(str(model_path), device=device, session=session)


class CellONNXInferDFINE(ONNXInferenceBase):
    def __init__(
        self,
        model_path,
        device: str = "gpu",
        tile_size=512,
        depth16=True,
        normalize_scheme: str = "v2",
        mean=None,
        std=None,
        session=None,
    ):
        self.mean, self.stdinv = self.get_normalization_values(mean, std, depth16, normalize_scheme)

        self.model_path = model_path
        self.provider = self._resolve_provider(device)

        self.session = session
        if self.session is None and self.model_path is not None:
            self.session = ort.InferenceSession(
                self.model_path,
                providers=[self.provider],
            )
        self.tile_size = tile_size

    def preprocess(self, input_img: np.array, tile_size: int = 512) -> np.array:
        # input is a numpy array of size (512, 512, 3)
        if len(input_img.shape) != 3:
            print("error input must have three dimensions X,Y,C")
        input = input_img.copy()
        # Pad the image if size is not standard
        if input.shape[1] != tile_size or input.shape[2] != tile_size:
            input, _ = self._pad_img(input, tile_size, (-1, -1))

        input = input.astype("float32") / 65535.0

        # now we add one dimension at the beginning (batch dimension)
        input = input[np.newaxis, ...].astype("float32")
        input = np.transpose(input, (0, 3, 1, 2)).astype("float32")

        return input

    def _model_forward(self, input_im):
        # run onnx inference
        orig_target_sizes = np.array([input_im.shape[2:4]], dtype="int64")
        return self.session.run(None, {"images": input_im, "orig_target_sizes": orig_target_sizes})

    def predict(self, input, prob_thresh=0.5, iou_th=0.5):
        input = self.preprocess(input, self.tile_size)
        # run onnx inference
        results_ort = self._model_forward(input)
        results = self.postprocess(results_ort, prob_thresh, iou_th)
        return results

    def postprocess(self, results_ort, prob_thresh, iou_th):
        boxes = results_ort[1][results_ort[2] > prob_thresh]
        scores = results_ort[2][results_ort[2] > prob_thresh]

        if iou_th > 0:
            keep_indices = nms(boxes, scores, iou_th)

            # Filter the boxes and scores
            boxes = boxes[keep_indices]
            scores = scores[keep_indices]

        # stack scores and bboxes
        scores = scores.reshape(-1, 1)
        boxes = np.hstack((boxes, scores))

        return boxes
