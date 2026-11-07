"""格鲁TALK 相遇 (user 2026-11-06): reading the window and choosing people."""

import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from src.tasks.glu_talk import screen

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "glu_talk"
# Crops of 1080p frames at (495, 300), bd2 session 2026-11-06.
CROP_ORIGIN = (495, 300)


def frame_with(name: str) -> np.ndarray:
    crop = cv2.imread(str(FIXTURES / name))
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    x, y = CROP_ORIGIN
    frame[y : y + crop.shape[0], x : x + crop.shape[1]] = crop
    return frame


def box(name: str, x: float, y: float, width: float = 120, height: float = 24):
    return SimpleNamespace(name=name, x=x - width / 2, y=y - height / 2, width=width, height=height)


class HeaderTest(unittest.TestCase):
    def test_remaining_count(self):
        self.assertEqual(3, screen.read_remaining("GLU TALK 今日的剩余相遇 | 3"))
        self.assertEqual(0, screen.read_remaining("今日的剩余相遇丨0"))
        self.assertEqual(2, screen.read_remaining("今日的剩余相遇2"))
        self.assertIsNone(screen.read_remaining("GLU TALK"))

    def test_dialog_free_only_with_a_count_and_nothing_paid(self):
        free = "保健部 EP.07 第7次相遇 是否要进行相遇事件? 可进行次数：2次 每日免费补充3次相遇事件次数。 取消 确认"
        self.assertEqual(2, screen.read_dialog_count(free))
        self.assertTrue(screen.dialog_is_free(free))
        new_bond = "被封印的欲望 是否要进行相遇事件? 可进行次数：3次 新的缘分仅可使用每日免费补充的次数进行相遇。"
        self.assertTrue(screen.dialog_is_free(new_bond))
        self.assertFalse(screen.dialog_is_free("是否要进行相遇事件? 可进行次数：0次"))
        self.assertFalse(screen.dialog_is_free("可进行次数：1次 消耗钻石补充"))
        self.assertFalse(screen.dialog_is_free("是否要进行相遇事件?"))


class HeartTest(unittest.TestCase):
    def test_hearts_found_on_the_chat_tab(self):
        hearts = screen.find_hearts(frame_with("list_chats_tab.png"))
        self.assertEqual([406, 500, 594, 688, 782], [y + h // 2 for _x, y, _w, h in hearts])
        self.assertTrue(all(590 <= x <= 615 for x, _y, _w, _h in hearts))

    def test_hearts_found_on_the_people_tab(self):
        self.assertEqual(4, len(screen.find_hearts(frame_with("list_people_tab_bottom.png"))))
        self.assertEqual(4, len(screen.find_hearts(frame_with("list_people_tab_middle.png"))))

    def test_digit_image_is_dark_ink_on_white(self):
        frame = frame_with("list_people_tab_bottom.png")
        image = screen.heart_digit_image(frame, screen.find_hearts(frame)[1])  # 「1」
        ink = int((image[:, :, 0] == 0).sum())
        self.assertGreater(ink, 100)
        self.assertGreater(int((image[:, :, 0] == 255).sum()), 10 * ink)

    def test_level_text(self):
        self.assertEqual(7, screen.read_level("7"))
        self.assertEqual(10, screen.read_level("10"))
        self.assertIsNone(screen.read_level(""))
        self.assertIsNone(screen.read_level("12"))


class RowTest(unittest.TestCase):
    def test_name_right_of_the_heart_without_digit_or_badge(self):
        boxes = [
            box("6 被封印的欲望 阿奇拉", 700, 594, width=220),
            box("1", 976, 600, width=20),
            box("这才对嘛！早这样不就好了！", 690, 629, width=220),
        ]
        self.assertEqual("被封印的欲望 阿奇拉", screen.row_name(boxes, 594))

    def test_choose_below_ten_highest_first(self):
        rows = [
            screen.Row("代号〇 爱丽洁", 10, 406),
            screen.Row("新进员工 内布利斯", 2, 782),
            screen.Row("战地医疗兵 格兰希特", 6, 500),
            screen.Row("被封印的欲望 阿奇拉", 6, 594),
            screen.Row("明月 达非", 1, 860),
            screen.Row("保健部 泰瑞丝", 6, 688),
            screen.Row("读不到", None, 900),
        ]
        picked = screen.choose(rows)
        self.assertEqual(
            ["战地医疗兵 格兰希特", "被封印的欲望 阿奇拉", "保健部 泰瑞丝", "新进员工 内布利斯", "明月 达非"],
            [row.name for row in picked],
        )
        self.assertEqual(["明月 达非"], [row.name for row in screen.choose(rows, 2)])


class ChatTest(unittest.TestCase):
    def test_reply_under_send(self):
        step = screen.chat_step(
            [box("因为我要亲自…给你做饭！", 1256, 714), box("发送消息", 1090, 768), box("你要给我做饭?", 1264, 814)]
        )
        self.assertEqual("reply", step.kind)
        self.assertEqual("你要给我做饭?", step.box.name)

    def test_send_without_its_reply_yet_waits(self):
        self.assertEqual("wait", screen.chat_step([box("发送消息", 1090, 768)]).kind)
        self.assertEqual("wait", screen.chat_step([box("嘿嘿，好像真是这样。", 1234, 444)]).kind)

    def test_card_to_start(self):
        step = screen.chat_step(
            [box("相遇事件", 1173, 669), box("EP.07", 1386, 669), box("第7次相遇", 1180, 721), box("进行相遇事件", 1288, 813)]
        )
        self.assertEqual("start", step.kind)

    def test_lowest_mark_wins(self):
        # The earlier reply and card stay in the history above the new card.
        step = screen.chat_step(
            [box("发送消息", 1090, 340), box("好的", 1264, 380), box("完成相遇事件", 1288, 500), box("进行相遇事件", 1288, 813)]
        )
        self.assertEqual("start", step.kind)
        done = screen.chat_step([box("进行相遇事件", 1288, 400), box("完成相遇事件", 1288, 700)])
        self.assertEqual("done", done.kind)


if __name__ == "__main__":
    unittest.main()
