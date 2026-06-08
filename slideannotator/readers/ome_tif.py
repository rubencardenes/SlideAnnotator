import numpy as np
import pyvips

from .base import ImageReader, _best_pyramid_level, _parse_ome_xml


def _vips2numpy(vi: pyvips.Image) -> np.ndarray:
    format_to_dtype = {
        "uchar": np.uint8,
        "char": np.int8,
        "ushort": np.uint16,
        "short": np.int16,
        "uint": np.uint32,
        "int": np.int32,
        "float": np.float32,
        "double": np.float64,
        "complex": np.complex64,
        "dpcomplex": np.complex128,
    }
    mem = vi.write_to_memory()
    arr = np.frombuffer(mem, dtype=format_to_dtype[vi.format])
    reshaped = arr.reshape((vi.height, vi.width, vi.bands)).copy()
    # Squeeze singleton dimensions: (h, w, 1) → (h, w)
    return np.squeeze(reshaped)


class ImageReaderOmeTif(ImageReader):
    def _load_metadata(self):
        try:
            self.img = pyvips.Image.new_from_file(self.filepath)
        except pyvips.error.Error as e:
            print(f"Failed to open OME-TIFF: {e}")
            return

        self.metadata["width"] = self.img.width
        self.metadata["height"] = self.img.height
        self.metadata["num_scenes"] = 1

        if "n-subifds" in self.img.get_fields():
            num_levels = self.img.get("n-subifds") + 1
            self.metadata["pyramid_levels"] = num_levels
            pyramid_info = []
            for k in range(num_levels):
                try:
                    kwargs = {} if k == 0 else {"subifd": k - 1}
                    lvl = pyvips.Image.new_from_file(self.filepath, page=0, **kwargs)
                    pyramid_info.append(
                        {
                            "level": k,
                            "factor": round(self.img.width / lvl.width),
                            "width": lvl.width,
                            "height": lvl.height,
                        }
                    )
                except pyvips.error.Error as e:
                    print(f"Warning: could not load pyramid level {k}: {e}")
                    break
            self.metadata["pyramid_info"] = pyramid_info

        try:
            if "image-description" not in self.img.get_fields():
                fields = self.img.get_fields()
                n = self.img.get("n-pages") if "n-pages" in fields else self.img.bands
                self.metadata["num_channels"] = n
                return
            _parse_ome_xml(self.img.get("image-description"), self.metadata)
        except Exception as e:
            print(f"Failed to parse OME-TIFF metadata: {e}")

    def get_region(self, x: int, y: int, w: int, h: int, channel: int) -> np.ndarray:
        img = pyvips.Image.new_from_file(self.filepath, page=channel)
        return _vips2numpy(img.crop(x, y, w, h))

    def get_downsampled(self, factor: int, channel: int) -> np.ndarray:
        level, level_factor = _best_pyramid_level(factor, self.metadata["pyramid_levels"])
        kwargs = {"page": channel} if level == 0 else {"page": channel, "subifd": level - 1}
        img = pyvips.Image.new_from_file(self.filepath, **kwargs)
        remaining = factor / level_factor
        if remaining > 1.0:
            img = img.shrink(remaining, remaining)
        return _vips2numpy(img)
