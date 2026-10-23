"""A popup's closing spot is not pressed twice in a row while the popup fades.

Live 4K clone 2026-10-23: 恭喜晋级's 确认 was pressed by the shared popup
closer, the fading page was still read on the next frame, and the PVP entry
pressed the same spot again: that press opened 战场角色设置 behind it and
镜中之战 failed 「未能进入 PVP 箱庭」.
"""

import unittest
from unittest import mock

from src.tasks import BaseBD2Task as base


class _Task:
    press_dismiss = base.BaseBD2Task.press_dismiss

    def __init__(self):
        self.clicks = []
        self.slept = []

    def operate_click(self, x, y, after_sleep=0):
        self.clicks.append((x, y))

    def sleep(self, seconds):
        self.slept.append(seconds)

    def info_set(self, *args):
        pass


class PressDismissTest(unittest.TestCase):
    def test_same_spot_moments_later_is_not_pressed(self):
        task = _Task()
        with mock.patch.object(base.time, "monotonic", side_effect=[10.0, 10.1, 11.5]):
            self.assertTrue(task.press_dismiss(0.4995, 0.929, 1.0, "确认"))
            self.assertFalse(task.press_dismiss(0.4995, 0.929, 1.0, "恭喜晋级"))
        self.assertEqual(task.clicks, [(0.4995, 0.929)])
        self.assertTrue(task.slept)  # waits out the fade before looking again

    def test_same_spot_after_the_fade_is_pressed_again(self):
        task = _Task()
        times = [10.0, 10.1, 10.1 + base.DISMISS_REPRESS_SECONDS + 0.1, 20.0]
        with mock.patch.object(base.time, "monotonic", side_effect=times):
            task.press_dismiss(0.5, 0.93)
            self.assertTrue(task.press_dismiss(0.5, 0.93))
        self.assertEqual(len(task.clicks), 2)

    def test_another_spot_is_pressed_at_once(self):
        task = _Task()
        with mock.patch.object(base.time, "monotonic", side_effect=[10.0, 10.1, 10.5, 10.6]):
            task.press_dismiss(0.5, 0.93)
            self.assertTrue(task.press_dismiss(0.6, 0.75))
        self.assertEqual(len(task.clicks), 2)


if __name__ == "__main__":
    unittest.main()
