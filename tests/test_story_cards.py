"""游戏卡珍藏集 rows, read live on the bd2 session 2026-10-22."""

import unittest
from types import SimpleNamespace

import numpy as np

from src.utils import story_cards


def _box(name, x, y, width=120, height=24):
    return SimpleNamespace(name=name, x=x - width / 2, y=y - height / 2, width=width, height=height)


class RowHeaderTest(unittest.TestCase):
    def test_the_master_rows_subtitle_is_not_the_story_row(self):
        boxes = [
            _box("店长游戏卡2／2", 210, 142),
            _box("「棕色尘埃2」主线剧情游戏卡", 470, 142, 220),
            _box("剧情游戏卡16／20", 248, 428),
            _box("「棕色尘埃2」过往剧情游戏卡", 465, 428, 220),
        ]
        self.assertEqual(428, _centre_y(story_cards.row_header(boxes, story_cards.STORY_ROW_TITLES)))
        self.assertEqual(142, _centre_y(story_cards.row_header(boxes, story_cards.MASTER_ROW_TITLES)))
        self.assertIsNone(story_cards.row_header(boxes[:2], story_cards.STORY_ROW_TITLES))


class DifficultyBannerTest(unittest.TestCase):
    """2026-10-23: 「Ⅱ 可进行困难难度」 under a card's art; its first clear pays 钻石."""

    def test_the_card_above_the_top_left_banner_is_clicked(self):
        boxes = [
            _box("剧情游戏卡20／20", 248, 330),
            _box("可进行困难难度", 1095, 270, 140),
            _box("可进行困难难度", 290, 270, 140),
            _box("可进行极难难度", 290, 837, 140),
        ]
        self.assertEqual(("可进行困难难度", (290, 170)), story_cards.difficulty_card(boxes))

    def test_traditional_and_very_hard_banners_count(self):
        self.assertEqual("可進行極難難度", story_cards.difficulty_card([_box("可進行極難難度", 500, 600)])[0])

    def test_no_banner(self):
        self.assertIsNone(story_cards.difficulty_card([_box("剧情游戏卡20／20", 248, 330)]))


class RewardsSwitchTest(unittest.TestCase):
    def _frame(self, bgr):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        left, top, right, bottom = story_cards.REWARDS_SWITCH_LEFT
        frame[top:bottom, left:right] = bgr
        return frame

    def test_gold_left_half_is_on(self):
        # live 2026-10-23 samples
        self.assertTrue(story_cards.rewards_switch_on(self._frame((62, 142, 182))))
        self.assertFalse(story_cards.rewards_switch_on(self._frame((210, 218, 222))))


def _centre_y(box):
    return box.y + box.height / 2


if __name__ == "__main__":
    unittest.main()
