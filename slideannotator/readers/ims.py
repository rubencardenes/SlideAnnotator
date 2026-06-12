import numpy as np

from .base import ImageReader, _to_microns


def _decode_ims_attr(v) -> str:
    """Imaris stores string attributes as byte arrays — join and decode."""
    if hasattr(v, "tobytes"):
        return v.tobytes().decode("utf-8", errors="replace").rstrip("\x00")
    return str(v)


class ImageReaderIms(ImageReader):
    """Reader for Imaris HDF5 (.ims) files.

    Structure: DataSet/ResolutionLevel {N}/TimePoint 0/Channel {C}/Data
    Data arrays are (Z, Y, X); for 2-D slides Z == 1.
    Metadata lives under DataSetInfo/Image and DataSetInfo/Channel {C}.
    """

    def __init__(self, filepath: str):
        import h5py

        self._f = h5py.File(filepath, "r")
        self._res_keys: list[str] = []
        super().__init__(filepath)

    def close(self):
        self._f.close()

    def __del__(self):
        try:
            self._f.close()
        except Exception:
            pass

    def _load_metadata(self):
        dsi = self._f["DataSetInfo"]
        img_attrs = dsi["Image"].attrs

        width = int(_decode_ims_attr(img_attrs["X"]))
        height = int(_decode_ims_attr(img_attrs["Y"]))
        self.metadata["width"] = width
        self.metadata["height"] = height

        num_channels = sum(1 for k in dsi.keys() if k.startswith("Channel "))
        self.metadata["num_channels"] = num_channels
        self.metadata["channel_names"] = [
            _decode_ims_attr(dsi[f"Channel {i}"].attrs.get("Name", b""))
            for i in range(num_channels)
        ]

        try:
            ext_max0 = float(_decode_ims_attr(img_attrs["ExtMax0"]))
            ext_max1 = float(_decode_ims_attr(img_attrs["ExtMax1"]))
            unit = _decode_ims_attr(img_attrs.get("Unit", b"")).strip()
            if not unit:
                unit = "µm"  # Imaris default
            self.metadata["pixel_size_x"] = _to_microns(ext_max0 / width, unit)
            self.metadata["pixel_size_y"] = _to_microns(ext_max1 / height, unit)
        except Exception:
            pass

        ds = self._f["DataSet"]
        self._res_keys = sorted(ds.keys())
        num_levels = len(self._res_keys)
        self.metadata["pyramid_levels"] = num_levels

        # Level 0 data dimensions (may be padded beyond image dimensions)
        level0_data = ds[self._res_keys[0]]["TimePoint 0"]["Channel 0"]["Data"]
        _, l0_w = level0_data.shape[1], level0_data.shape[2]

        pyr_info = []
        for i, res_key in enumerate(self._res_keys):
            data = ds[res_key]["TimePoint 0"]["Channel 0"]["Data"]
            lh, lw = data.shape[1], data.shape[2]
            factor = max(1, round(l0_w / lw))
            pyr_info.append({"level": i, "factor": factor, "width": lw, "height": lh})
        self.metadata["pyramid_info"] = pyr_info

    def _best_level(self, factor: int) -> tuple[int, int]:
        """Return (level_index, level_factor) for the largest level_factor ≤ factor."""
        best_level, best_factor = 0, 1
        for entry in self.metadata["pyramid_info"]:
            lf = entry["factor"]
            if lf <= factor and lf >= best_factor:
                best_level = entry["level"]
                best_factor = lf
        return best_level, best_factor

    def _level_data(self, level: int, channel: int):
        res_key = self._res_keys[level]
        return self._f[f"DataSet/{res_key}/TimePoint 0/Channel {channel}/Data"]

    def get_region(self, x: int, y: int, w: int, h: int, channel: int) -> np.ndarray:
        data = self._level_data(0, channel)
        return data[0, y : y + h, x : x + w]

    def get_downsampled(self, factor: int, channel: int) -> np.ndarray:
        level, level_factor = self._best_level(factor)
        arr = self._level_data(level, channel)[0]  # (Y, X)
        remaining = factor / level_factor
        if remaining > 1.0:
            out_h = int(arr.shape[0] / remaining)
            out_w = int(arr.shape[1] / remaining)
            row_idx = np.round(np.linspace(0, arr.shape[0] - 1, out_h)).astype(int)
            col_idx = np.round(np.linspace(0, arr.shape[1] - 1, out_w)).astype(int)
            arr = arr[np.ix_(row_idx, col_idx)]
        return arr
