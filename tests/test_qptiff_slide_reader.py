from pathlib import Path

import numpy as np
from PIL import Image, TiffImagePlugin

from slideannotator.readers import open_slide
from slideannotator.readers.qptiff_slide_reader import QptiffSlideReader


def _description(image_type: str, name: str = "", color: str = "") -> str:
    return (
        "<PerkinElmer-QPI-ImageDescription>"
        f"<ImageType>{image_type}</ImageType>"
        f"<Name>{name}</Name>"
        f"<Color>{color}</Color>"
        "</PerkinElmer-QPI-ImageDescription>"
    )


def _write_qptiff(path: Path) -> None:
    specifications = [
        ((32, 24), 10, _description("FullResolution", "DAPI", "0,0,255")),
        ((32, 24), 20, _description("FullResolution", "FITC", "0,255,0")),
        ((8, 6), 99, _description("Thumbnail")),
        ((16, 12), 30, _description("ReducedResolution", "DAPI", "0,0,255")),
        ((16, 12), 40, _description("ReducedResolution", "FITC", "0,255,0")),
        ((12, 9), 88, _description("Overview")),
    ]
    images = []
    for size, value, description in specifications:
        image = Image.new("L", size, value)
        tags = TiffImagePlugin.ImageFileDirectory_v2()
        tags[270] = description
        # Pillow uses the per-frame encoderinfo for append_images frames.
        image.encoderinfo = {"tiffinfo": tags}
        images.append(image)
    images[0].save(
        path,
        format="TIFF",
        save_all=True,
        append_images=images[1:],
        tiffinfo=images[0].encoderinfo["tiffinfo"],
    )


def test_qptiff_discovers_channels_and_levels_around_auxiliary_pages(tmp_path: Path) -> None:
    path = tmp_path / "slide.qptiff"
    _write_qptiff(path)

    reader = QptiffSlideReader(path)
    try:
        assert reader.dimensions == (32, 24)
        assert reader.level_dimensions == [(32, 24), (16, 12)]
        assert reader.level_downsamples == [1.0, 2.0]
        assert [(channel.name, channel.color) for channel in reader.channels] == [
            ("DAPI", (0, 0, 255)),
            ("FITC", (0, 255, 0)),
        ]
        assert reader.metadata["bit_depth"] == 8

        full = reader.read_tile(0, 0, 0)
        reduced = reader.read_tile(1, 0, 0)
        assert full.shape == (2, 512, 512)
        assert reduced.shape == (2, 512, 512)
        np.testing.assert_array_equal(full[:, 0, 0], [10, 20])
        np.testing.assert_array_equal(reduced[:, 0, 0], [30, 40])
        assert np.all(full[:, 24:, :] == 0)
        assert np.all(reduced[:, 12:, :] == 0)
    finally:
        reader.close()


def test_open_slide_routes_qptiff_to_dedicated_reader(tmp_path: Path) -> None:
    path = tmp_path / "slide.qptiff"
    _write_qptiff(path)

    reader = open_slide(path)
    try:
        assert isinstance(reader, QptiffSlideReader)
    finally:
        reader.close()
