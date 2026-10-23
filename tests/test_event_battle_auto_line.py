"""活动每日战斗: the game's own auto-battle line anywhere on screen keeps the
watch on the battle (player 2026-10-23, v0.2.9: 「8 秒不在战斗中也没认出结果
画面」 while the way home's whole-screen read found the battle).  Nothing is
pressed for it.
"""

import unittest
from unittest import mock

from src.tasks import EventBattleTask as event_module
from src.tasks.EventBattleTask import CHALLENGE_MODE
from tests.test_event_battle_defeat import BATTLE, ScreenTask, box

AUTO_LINE = {"full": ["自动战斗中", "结束自动战斗 ESC"]}
RESULT = {"buttons": ["返回"]}


def _task(frames):
    now = [0.0]

    def clock():
        now[0] += 1.0
        return now[0]

    task = ScreenTask([BATTLE]).task
    frames = iter(frames)
    task.capture_frame = lambda: next(frames)
    inner = task._roi_boxes
    task._roi_boxes = lambda frame, roi, name: (
        [box(t) for t in frame.get("full", [])] if roi is None else inner(frame, roi, name)
    )
    task._wait_for_stage_page = lambda mode, timeout=0, quiet=False: False
    task.tap_escape = lambda after_sleep=0: (_ for _ in ()).throw(AssertionError("pressed Esc"))
    task._leave_result_screen = lambda: True
    return task, clock


class AutoLineTest(unittest.TestCase):
    def test_the_games_auto_line_is_still_the_battle(self):
        task, clock = _task([BATTLE] + [AUTO_LINE] * 30 + [RESULT] * 2)
        with mock.patch.object(event_module, "monotonic", side_effect=clock):
            result = task._watch_auto_battle(5, CHALLENGE_MODE)

        self.assertEqual(5, result)
        self.assertEqual("", task._why)
        self.assertEqual([], task.clicks)  # no blank tap, no press

    def test_failure_waits_for_such_a_battle_before_the_way_home(self):
        task, clock = _task([AUTO_LINE] * 3 + [{}] * 5)
        with mock.patch.object(event_module, "monotonic", side_effect=clock):
            task._settle_before_recovery()
        self.assertEqual([], task.clicks)
        self.assertEqual("失败后等待战斗结束", task.info.get("当前阶段"))


if __name__ == "__main__":
    unittest.main()
