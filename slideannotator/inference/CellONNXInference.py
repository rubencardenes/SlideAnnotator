from .ONNXInferenceBase import ONNXInferenceBase
import onnxruntime as ort
import numpy as np
from loguru import logger

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
        self.mean, self.stdinv = self.get_normalization_values(
            mean, std, depth16, normalize_scheme
        )

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
        self.mean, self.stdinv = self.get_normalization_values(
            mean, std, depth16, normalize_scheme
        )

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
        return self.session.run(
            None, {"images": input_im, "orig_target_sizes": orig_target_sizes}
        )

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
    ):
        self.mean, self.stdinv = self.get_normalization_values(
            mean, std, depth16, normalize_scheme
        )

        self.model_path = model_path
        self.provider = self._resolve_provider(device)

        if self.model_path is not None:
            self.session = ort.InferenceSession(
                self.model_path,
                providers=[self.provider],
            )
        self.tile_size = tile_size

    def preprocess(
        self, input_img: np.array, tile_size: int = 512
    ) -> np.array:
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
        return self.session.run(
            None, {"images": input_im, "orig_target_sizes": orig_target_sizes}
        )

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
