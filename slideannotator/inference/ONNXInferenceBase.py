# Authors:     Ruben Cardenes, Adhithya Sankar
# Date:        Sept, 2022
# Copyright:   Ultivue
# File:        inference.py
# Description: Classes to do onnx inference for cell detection, semantic segmentation
#              on single tiles (CK segmentation) and semantic segmentation on
#              downsampled image (tissue detection)

import abc

import numpy as np


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


class ONNXInferenceBase(abc.ABC):
    """Base Class for Inference handling.

    Methods:
        _model_forward: Forward pass of the model.
        preprocess: preprocessing steps of the input.
        postprocess: postprocessing steps of the output.
        predict: model prediction pipeline.
    """

    @classmethod
    @abc.abstractmethod
    def _model_forward(self, input_dict: dict, **kwargs):
        """inference function. Here is where the model
        inference(forward pass) takes place.

        Args:
            input_dict (Dict): input dictionary.
        """
        pass

    @classmethod
    @abc.abstractmethod
    def predict(
        self,
        input_data: np.ndarray,
        **kwargs,
    ):
        """base predict function. Here is where
        the model inference pipeline is defined.

        Args:
            input_data (np.ndarray): model input.
        """
        pass

    @classmethod
    @abc.abstractmethod
    def preprocess(self, **kwargs):
        """base method for preprocessing. Input
        preprocessing takes place here.
        """
        pass

    @classmethod
    @abc.abstractmethod
    def postprocess(self, **kwargs):
        """base method for postprocessing. Output
        postprocessing takes place here.
        """
        pass

    @staticmethod
    def _resolve_provider(device: str) -> str:
        """returns ONNXRuntime Provider for inference
        session based on user input.

        Args:
            device (str): device to use for inference [cuda, cpu].

        Returns:
            str: Provider for Inferen Session.
        """
        if device.lower() in ["gpu", "cuda"]:
            provider = "CUDAExecutionProvider"
        elif device.lower() == "trt":
            provider = "TensorrtExecutionProvider"
        else:
            provider = "CPUExecutionProvider"

        return provider

    def get_normalization_values(self, mean, std, depth16, normalize_scheme):
        # Set default mean and std values based on the depth16 and normalize_scheme
        default_values = {
            "v0": ([123.675, 116.28, 103.53], [58.395, 57.12, 57.375]),
            "v1": ([500.0, 0.0, 4000.0], [1000.0, 1.0, 10000.0]),
            "v2": ([500.0, 0.0, 500.0], [1000.0, 1.0, 1000.0]),
        }
        if mean is None or std is None:
            if depth16:
                normalize_scheme = normalize_scheme
            else:
                normalize_scheme = "v0"

            mean, std = default_values.get(
                normalize_scheme, default_values.get("v2")
            )

        # Convert mean and std to numpy arrays of type np.float64 and reshape
        mean = np.float64(np.array(mean).reshape(1, -1))
        stdinv = 1 / np.float64(np.array(std).reshape(1, -1))

        return mean, stdinv

    def _pad_img(
        self,
        img_arr: np.ndarray,
        tile_size: int,
        pad_size: tuple[int, int] = (0, 0),
    ) -> np.ndarray:
        """pads image to tile_size if required. The padding adds zeros to the
           image so the original image remains in the top left corner

        Args:
            img_arr (np.ndarray): input image array to be padded.
            pad_size (Tuple[int, int]): amount odf padding (row, col)

        Returns:
            np.ndarray: padded array.
        """
        pad_r, pad_c = pad_size
        if pad_r == -1 and pad_c == -1:
            pad_r = self.tile_size - img_arr.shape[0]
            pad_c = self.tile_size - img_arr.shape[1]

        if pad_r or pad_c:
            if img_arr.ndim == 2:
                img_arr = np.pad(img_arr, ((0, pad_r), (0, pad_c)))
            else:
                img_arr = np.pad(img_arr, ((0, pad_r), (0, pad_c), (0, 0)))

        return img_arr, (pad_r, pad_c)
