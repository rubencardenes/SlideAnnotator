import numpy as np
import pylibCZIrw.czi as pyczi

from .base import ImageReader, _best_pyramid_level, _to_microns


class ImageReaderCzi(ImageReader):
    def __init__(self, filepath: str):
        self.czi = pyczi.CziReader(filepath)
        super().__init__(filepath)

    def __del__(self):
        try:
            self.czi.close()
        except Exception:
            pass

    def close(self):
        self.czi.close()

    def _load_metadata(self):
        try:
            meta = self.czi.metadata
            bbox = self.czi.total_bounding_box

            x_range = bbox.get("X", (0, 0))
            y_range = bbox.get("Y", (0, 0))
            full_w = x_range[1] - x_range[0]
            full_h = y_range[1] - y_range[0]
            self.metadata["width"] = full_w
            self.metadata["height"] = full_h

            c_range = bbox.get("C", (0, 0))
            self.metadata["num_channels"] = c_range[1] - c_range[0]
            self.metadata["num_scenes"] = len(self.czi.scenes_bounding_rectangle)

            # Pyramid info from metadata -> Information -> Image -> Dimensions -> S -> Scenes -> Scene
            scene_node = (
                meta.get("ImageDocument", {})
                .get("Metadata", {})
                .get("Information", {})
                .get("Image", {})
                .get("Dimensions", {})
                .get("S", {})
                .get("Scenes", {})
                .get("Scene", {})
            )
            if isinstance(scene_node, list):
                scene_node = scene_node[0] if scene_node else {}
            pyr_dict = scene_node.get("PyramidInfo", {})
            num_levels = int(pyr_dict.get("PyramidLayersCount", 1))
            pyr_factor = int(pyr_dict.get("MinificationFactor", 2))
            if num_levels < 1:
                num_levels = 1

            self.metadata["pyramid_levels"] = num_levels
            self.metadata["pyramid_info"] = [
                {
                    "level": k,
                    "factor": pyr_factor**k,
                    "width": max(1, full_w // (pyr_factor**k)),
                    "height": max(1, full_h // (pyr_factor**k)),
                }
                for k in range(num_levels)
            ]

            img_info = (
                meta.get("ImageDocument", {})
                .get("Metadata", {})
                .get("Information", {})
                .get("Image", {})
            )

            channels = img_info.get("Dimensions", {}).get("Channels", {}).get("Channel", [])
            if isinstance(channels, dict):
                channels = [channels]
            self.metadata["channel_names"] = [ch.get("@Name", "") for ch in channels]

            distances = (
                meta.get("ImageDocument", {})
                .get("Metadata", {})
                .get("Scaling", {})
                .get("Items", {})
                .get("Distance", [])
            )
            if isinstance(distances, dict):
                distances = [distances]
            for d in distances:
                val = float(d.get("Value", 0) or 0)
                if d.get("@Id") == "X":
                    self.metadata["pixel_size_x"] = _to_microns(val, "m")
                elif d.get("@Id") == "Y":
                    self.metadata["pixel_size_y"] = _to_microns(val, "m")

            objectives = (
                meta.get("ImageDocument", {})
                .get("Metadata", {})
                .get("Information", {})
                .get("Instrument", {})
                .get("Objectives", {})
                .get("Objective", {})
            )
            if isinstance(objectives, list):
                objectives = objectives[0] if objectives else {}
            mag = objectives.get("@NominalMagnification") or objectives.get("NominalMagnification")
            if mag:
                self.metadata["magnification"] = float(mag)

        except Exception as e:
            print(f"Failed to load CZI metadata: {e}")

    def get_region(self, x: int, y: int, w: int, h: int, channel: int) -> np.ndarray:
        return np.squeeze(self.czi.read(plane={"C": channel}, roi=(x, y, w, h)))

    def get_downsampled(self, factor: int, channel: int) -> np.ndarray:
        level, level_factor = _best_pyramid_level(factor, self.metadata["pyramid_levels"])
        zoom = 1.0 / level_factor
        arr = np.squeeze(self.czi.read(plane={"C": channel}, zoom=zoom))
        remaining = factor / level_factor
        if remaining > 1.0:
            out_h = int(arr.shape[0] / remaining)
            out_w = int(arr.shape[1] / remaining)
            row_idx = np.round(np.linspace(0, arr.shape[0] - 1, out_h)).astype(int)
            col_idx = np.round(np.linspace(0, arr.shape[1] - 1, out_w)).astype(int)
            arr = arr[np.ix_(row_idx, col_idx)]
        return arr
