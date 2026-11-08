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

    def test_episode_end_as_the_last_line(self):
        # Live 2026-11-08: 阿奇拉's talk after the day-before encounter.
        boxes = [
            box("你还真是什么话都能这么随口说出来啊?", 1290, 660),
            box("…反正你满意了，对吧？那就行了！", 1290, 750),
            box("EP7. 对话结束", 1270, 830),
        ]
        self.assertEqual("ended", screen.chat_step(boxes).kind)

    def test_line_under_the_episode_end_is_a_new_message(self):
        boxes = [box("EP7. 对话结束", 1270, 500), box("店长，在干嘛?", 1240, 600)]
        self.assertEqual("wait", screen.chat_step(boxes).kind)

    def test_old_episode_end_above_a_card(self):
        boxes = [box("EP2. 对话结束", 1270, 380), box("相遇事件", 1173, 669), box("进行相遇事件", 1288, 813)]
        self.assertEqual("start", screen.chat_step(boxes).kind)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += float(seconds)


def glu_task(clock: FakeClock, frames: list[tuple[str, str]]):
    """A GluTalkTask with the screen played from ``frames``: (kind, text) per
    look, kind window / reward / effect; the last one stays."""
    from src.tasks.GluTalkTask import GluTalkTask

    task = object.__new__(GluTalkTask)
    state = {"index": 0}
    task.clicks = []
    task.logs = []

    def capture_frame():
        frame = frames[min(state["index"], len(frames) - 1)]
        state["index"] += 1
        clock.sleep(0.3)
        return frame

    task.capture_frame = capture_frame
    task._reference_boxes = lambda frame, _roi, _name: [frame]
    task._boxes_text = lambda boxes: "" if boxes[0][0] == "window" else boxes[0][1]
    task._window_open = lambda frame: frame[0] == "window"
    task._header_text = lambda frame: frame[1]

    def click(*point, after_sleep=0.0):
        task.clicks.append(point)
        clock.sleep(after_sleep)

    task._click_reference = click
    task.log_info = lambda message, *_args, **_kwargs: task.logs.append(message)
    task.sleep = clock.sleep
    task._save_flow_diagnostic = lambda *_args, **_kwargs: None
    return task


class AfterSceneTest(unittest.TestCase):
    def setUp(self):
        from src.tasks import GluTalkTask as module

        self.module = module
        self.clock = FakeClock()
        self.old_monotonic = module.monotonic
        module.monotonic = self.clock

    def tearDown(self):
        self.module.monotonic = self.old_monotonic

    def test_window_before_the_reward_is_not_back(self):
        # Live 2026-11-08 提尔: the window with the count still 1, then the
        # reward and the picture over it.
        frames = [("window", "GLU TALK 今日的剩余相遇 | 1")] * 4 + [
            ("reward", "获得好感度奖励 澄心无邪兔女郎 提尔 50"),
            ("effect", "获得好感度特效！ 主界面设置"),
            ("effect", "获得好感度特效！ 主界面设置"),
            ("window", "GLU TALK 今日的剩余相遇 | 0"),
        ]
        task = glu_task(self.clock, frames)
        row = screen.Row("澄心无邪兔女郎 提尔", 2, 500)

        self.assertTrue(self.module.GluTalkTask._after_scene(task, row, 1))
        self.assertEqual(
            [screen.REWARD_TAP_POINT, screen.EFFECT_BACK_POINT, screen.EFFECT_BACK_POINT], task.clicks
        )

    def test_count_down_without_a_reward_is_back_after_a_moment(self):
        task = glu_task(self.clock, [("window", "GLU TALK 今日的剩余相遇 | 1")])
        row = screen.Row("水上乐园女王 威廉明娜", 3, 500)

        self.assertTrue(self.module.GluTalkTask._after_scene(task, row, 2))
        self.assertEqual([], task.clicks)
        self.assertLess(self.clock.now, self.module.AFTER_SCENE_WINDOW_SECONDS)

    def test_window_with_the_same_count_waits_for_the_reward_a_while(self):
        task = glu_task(self.clock, [("window", "GLU TALK 今日的剩余相遇 | 1")])
        row = screen.Row("澄心无邪兔女郎 提尔", 2, 500)

        self.assertTrue(self.module.GluTalkTask._after_scene(task, row, 1))
        self.assertGreaterEqual(self.clock.now, self.module.AFTER_SCENE_WINDOW_SECONDS)
        self.assertTrue(any("没看到好感度奖励" in line for line in task.logs))


class PlayChatTest(unittest.TestCase):
    def test_episode_end_moves_on_in_seconds(self):
        from src.tasks import GluTalkTask as module

        clock = FakeClock()
        old = module.monotonic
        module.monotonic = clock
        try:
            task = object.__new__(module.GluTalkTask)
            task._chat_boxes = lambda: [box("…那就行了！", 1290, 750), box("EP7. 对话结束", 1270, 830)]
            task.sleep = clock.sleep
            task.log_info = lambda *_args, **_kwargs: None
            task._save_flow_diagnostic = lambda *_args, **_kwargs: None
            step = module.GluTalkTask._play_chat(task, screen.Row("被封印的欲望 阿奇拉", 7, 500))
        finally:
            module.monotonic = old
        self.assertEqual("ended", step.kind)
        self.assertLess(clock.now, 10)


if __name__ == "__main__":
    unittest.main()
