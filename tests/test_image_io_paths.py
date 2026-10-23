"""Images are read and written through src/utils/image_io.py, never cv2.imread/imwrite.

On Windows cv2.imread/imwrite can't open a path with non-English letters (a
player's install under OneDrive\\桌面: every PVP template 「不存在或无法读取」,
2026-10-23).  Linux has no such limit, so the guard below is what keeps a new
cv2.imread out of src.
"""

import re
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.utils import image_io, task_vision
from src.utils.vision_models import TemplateSpec

ROOT = Path(__file__).resolve().parents[1]
DIRECT_FILE_CALL = re.compile(r"\bcv2\.(imread|imwrite)\s*\(")


class ImageIoPathTests(unittest.TestCase):
    def test_no_code_in_src_opens_an_image_file_with_cv2_directly(self):
        offenders = []
        for path in sorted((ROOT / "src").rglob("*.py")):
            if path.name == "image_io.py":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if DIRECT_FILE_CALL.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}")
        self.assertEqual(offenders, [], "use src.utils.image_io.read/write instead")

    def test_round_trip_under_a_chinese_folder(self):
        image = np.zeros((6, 8, 4), dtype=np.uint8)
        image[:, :4] = (10, 200, 30, 255)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "OneDrive" / "桌面" / "yes-bd2"
            folder.mkdir(parents=True)
            png = folder / "pvp-medals.png"
            self.assertTrue(image_io.write(png, image))
            np.testing.assert_array_equal(image_io.read(png, cv2.IMREAD_UNCHANGED), image)
            self.assertEqual(image_io.read(png, cv2.IMREAD_GRAYSCALE).shape, (6, 8))

            jpg = folder / "问题.jpg"
            self.assertTrue(image_io.write(jpg, image[:, :, :3], [cv2.IMWRITE_JPEG_QUALITY, 80]))
            self.assertEqual(image_io.read(jpg).shape, (6, 8, 3))

            gray, mask = task_vision.load_template(folder, TemplateSpec("medals", "pvp-medals.png"))
            self.assertEqual(gray.shape, (6, 8))

    def test_a_missing_or_empty_file_reads_as_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(image_io.read(Path(tmp) / "没有.png"))
            empty = Path(tmp) / "空.png"
            empty.write_bytes(b"")
            self.assertIsNone(image_io.read(empty))
            self.assertFalse(image_io.write(Path(tmp) / "没有" / "a.png", np.zeros((2, 2), np.uint8)))


if __name__ == "__main__":
    unittest.main()
