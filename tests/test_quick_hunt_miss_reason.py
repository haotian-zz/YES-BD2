"""A press 快速狩猎 does not make says why (player 1280x720 2026-10-24:
「未找到可点击 OCR 目标：选择金币航线」; Leo 「錯誤要寫原因 不要寫讀不到」)."""

import unittest

import numpy as np

from src.tasks.quick_hunt import _miss_reason


class MissReasonTest(unittest.TestCase):
    def test_it_names_what_was_read_and_the_small_window(self):
        frame = np.zeros((720, 1280, 3), np.uint8)
        reason = _miss_reason("选择金币航线", "史莱姆  狩猎场", frame)
        self.assertIn("「选择金币航线」没按", reason)
        self.assertIn("读到的字是「史莱姆 狩猎场」", reason)
        self.assertIn("1280×720", reason)
        self.assertIn("1920×1080", reason)

    def test_nothing_read_on_a_full_size_window(self):
        frame = np.zeros((1080, 1920, 3), np.uint8)
        reason = _miss_reason("选择金币航线", "", frame)
        self.assertEqual("「选择金币航线」没按：那一区一个字都没读到", reason)


if __name__ == "__main__":
    unittest.main()
