"""A card whose story was never played opens on its talk (bd2 session
2026-11-01, 角色卡3 「代号S莎拉」): the entry wait skips it (F2, then the
「跳过对话」 确认) and the collector leaves the card (user: 退出这张卡带)."""

import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from src.tasks.map_trade.navigator import Navigator
from src.utils import story_push

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "map_trade" / "cp3_story_talk_top_right.png"


def talk_frame():
    frame = np.full((1080, 1920, 3), 40, np.uint8)
    frame[0:150, 1500:1920] = cv2.imread(str(FIXTURE))
    return frame


def navigator(boxes=()):
    nav = object.__new__(Navigator)
    nav.clicks, nav.status = [], []
    nav.vision = SimpleNamespace(
        click_reference=lambda x, y, after_sleep=0.0: nav.clicks.append((x, y)),
        click_client=lambda point, _shape, after_sleep=0.0: nav.clicks.append(point),
        ocr_boxes=lambda *_a, **_k: list(boxes),
        simplify=lambda value: value,
    )
    nav._status = lambda key, value: nav.status.append(value)
    return nav


class StoryTalkSkipTest(unittest.TestCase):
    def test_the_live_talk_is_seen_and_skipped(self):
        nav = navigator()
        self.assertTrue(nav._skip_story_talk(talk_frame()))
        self.assertEqual([story_push.TALK_SKIP_POINT], nav.clicks)
        self.assertTrue(nav.story_talk_skipped)

    def test_a_half_size_frame_is_read_too(self):
        nav = navigator()
        self.assertTrue(nav._skip_story_talk(cv2.resize(talk_frame(), (1280, 720))))

    def test_no_talk_no_press(self):
        nav = navigator()
        self.assertFalse(nav._skip_story_talk(np.full((1080, 1920, 3), 40, np.uint8)))
        self.assertEqual([], nav.clicks)
        self.assertFalse(nav.story_talk_skipped)

    def test_the_skip_dialog_is_confirmed_after_the_press(self):
        boxes = [
            SimpleNamespace(name="跳过对话", x=900, y=400, width=120, height=30),
            SimpleNamespace(name="取消", x=820, y=765, width=60, height=30),
            SimpleNamespace(name="确认", x=1015, y=765, width=60, height=30),
        ]
        nav = navigator(boxes)
        nav.story_talk_skipped = True
        self.assertTrue(nav._skip_story_talk(np.full((1080, 1920, 3), 40, np.uint8)))
        self.assertEqual([(1045, 780)], nav.clicks)


if __name__ == "__main__":
    unittest.main()
