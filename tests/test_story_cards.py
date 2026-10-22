"""游戏卡珍藏集 rows, read live on the bd2 session 2026-10-22."""

import unittest
from types import SimpleNamespace

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


def _centre_y(box):
    return box.y + box.height / 2


if __name__ == "__main__":
    unittest.main()
