import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2

from src.tasks.claim_page import claim_button_dimmed
from src.tasks.TalentStarUpTask import script_talent, star_up_targets

FIXTURES = Path(__file__).parent / "fixtures" / "talent"


def box(name, x, y, width=60, height=30):
    return SimpleNamespace(name=name, x=x, y=y, width=width, height=height)


class StarUpTargetsTest(unittest.TestCase):
    """Live 2026-10-24 panel: 探查(高手, bar not full), three 吸收 and three 召集
    with 升星 under most, 料理, and 疾速 (not a script talent) with 升星."""

    def test_only_script_talents_with_a_button_under_them(self):
        boxes = [
            box("探查", 160, 912),
            box("吸收", 283, 912),
            box("升星", 283, 985),
            box("召集", 683, 912),
            box("升星", 683, 985),
            box("料理", 1398, 912),
            box("疾速", 1521, 912),
            box("升星", 1521, 985),
            # The usage line and the level under a card are not names.
            box("每日使用5", 270, 890, width=90),
            box("高手", 160, 975),
        ]
        self.assertEqual(
            [("吸收", (313, 1000)), ("召集", (713, 1000))],
            star_up_targets(boxes),
        )

    def test_traditional_caption_and_subdue_alias(self):
        self.assertEqual("召集", script_talent("召集"))
        self.assertEqual("探查", script_talent("探查"))
        self.assertEqual("压制", script_talent("壓制"))
        self.assertEqual("", script_talent("疾速"))

    def test_button_far_from_any_name_is_ignored(self):
        self.assertEqual([], star_up_targets([box("吸收", 283, 912), box("升星", 900, 985)]))


class StarUpButtonTest(unittest.TestCase):
    """The 天赋 page's 「升星 4,000」 pill, lit with a full bar and grey after."""

    LABEL = box("升星4,000", 150, 20, width=150, height=40)

    def test_lit_button_is_not_dimmed(self):
        frame = cv2.imread(str(FIXTURES / "star_up_lit.png"))
        self.assertFalse(claim_button_dimmed(frame, self.LABEL))

    def test_grey_button_is_dimmed(self):
        frame = cv2.imread(str(FIXTURES / "star_up_grey.png"))
        self.assertTrue(claim_button_dimmed(frame, self.LABEL))


if __name__ == "__main__":
    unittest.main()
