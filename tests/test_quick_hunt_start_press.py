"""A lost 「狩猎」 press is pressed once more while its dialog is still up.

bd2 会话 2026-11-02: 水之洞穴's 狩猎 60 press was swallowed; the dialog
(取消 / 狩猎 60) stayed until the stuck watch pressed Esc and the whole
quick hunt failed.
"""

import itertools
import unittest
from unittest import mock

from src.tasks import quick_hunt

DIALOG = "固定奖励 300 取消 狩猎60"
REWARD = "点击画面即可返回"


class StartPressTest(unittest.TestCase):
    def _task(self, screens):
        from src.tasks.QuickHuntTask import QuickHuntTask

        task = object.__new__(QuickHuntTask)
        task.config = {"快速狩猎结算等待秒数": 30}
        task.infos, task.clicks = [], []
        task.log_info = lambda message, **k: task.infos.append(message)
        task.sleep = lambda *a: None
        task.capture_frame = lambda: None
        shown = iter(screens)
        task._current = None

        def ocr(_frame, _roi, name, **k):
            if name.endswith("-奖励"):
                task._current = next(shown, screens[-1])
                return REWARD if task._current == "reward" else ""
            return DIALOG if task._current == "dialog" else ""

        task._quick_hunt_ocr_text = ocr
        task._quick_hunt_click_ocr = lambda patterns, roi, timeout, name, **k: (
            task.clicks.append(name) or True
        )
        task._quick_hunt_close_reward = lambda _stage: True
        return task

    def _run(self, task):
        clock = itertools.count(0, 0.5)
        never = mock.Mock()
        never.over.return_value = False
        with mock.patch.object(quick_hunt, "monotonic", lambda: next(clock)), \
                mock.patch.object(quick_hunt, "load_wait", return_value=never), \
                mock.patch.object(quick_hunt, "scene_at_press", return_value=None), \
                mock.patch.object(quick_hunt, "is_loading_dark", return_value=False):
            return task._quick_hunt_wait_result("水属性圣石")

    def test_dialog_still_up_is_pressed_once_more(self):
        task = self._task(["dialog"] * 6 + ["", "reward"])
        self.assertEqual("done", self._run(task))
        self.assertEqual(["水属性圣石-再按开始狩猎"], task.clicks)
        self.assertTrue(any("再按一次" in line for line in task.infos))

    def test_only_one_extra_press(self):
        task = self._task(["dialog"] * 20 + ["reward"])
        self.assertEqual("done", self._run(task))
        self.assertEqual(1, len(task.clicks))

    def test_press_that_worked_is_not_repeated(self):
        task = self._task(["", "", "reward"])
        self.assertEqual("done", self._run(task))
        self.assertEqual([], task.clicks)


if __name__ == "__main__":
    unittest.main()
