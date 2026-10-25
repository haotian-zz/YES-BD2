"""Leaving the cooking list (player v0.2.11 2026-10-24, 1080p windowed:
「料理：退出后未确认回到商人旁的箱庭」 then 「想把技能组切回原本的第3组，但现在
认到的是认不出」).  A swallowed 返回 is pressed once more while the list still
shows, and the skill-group buttons are never pressed off the field."""

import unittest
from types import SimpleNamespace
from unittest import mock

from src.tasks.map_trade import trader_cooking
from src.tasks.map_trade.trader import Trader


class _Task:
    def __init__(self):
        self.clicks = []
        self.logs = []

    def operate_click(self, x, y, after_sleep=0.0):
        self.clicks.append((x, y))

    def sleep(self, _seconds):
        pass

    def log_info(self, message, **_kwargs):
        self.logs.append(("info", message))

    def log_warning(self, message, **_kwargs):
        self.logs.append(("warning", message))


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 0.5
        return self.now


def _trader(presses_needed):
    """The list closes after ``presses_needed`` 返回 presses (0: never)."""
    task = _Task()
    state = {"backs": 0}
    trader = object.__new__(Trader)
    trader.task = task
    trader._status = lambda *_a: None
    trader._cooking_opened = True

    def on_field():
        return bool(presses_needed) and state["backs"] >= presses_needed

    trader.navigator = SimpleNamespace(wait_for_q_sp6_sandbox=lambda _timeout: on_field())
    snapshot = SimpleNamespace(frame="list")
    trader._recover_cooking_list = lambda: True
    trader._wait_for_cooking_list = lambda _timeout: None if on_field() else snapshot
    trader._cooking_list_snapshot = lambda *_a, **_k: None if on_field() else snapshot

    def back(_frame, *, context):
        state["backs"] += 1
        task.logs.append(("back", context))

    trader._click_cooking_back = back
    return trader, task, state


class CookingExitTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(trader_cooking, "monotonic", _Clock())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_one_back_is_enough_when_it_takes(self):
        trader, task, state = _trader(presses_needed=1)
        self.assertTrue(trader._leave_cooking_to_q_sp6())
        self.assertEqual(1, state["backs"])

    def test_a_swallowed_back_is_pressed_once_more(self):
        trader, task, state = _trader(presses_needed=2)
        self.assertTrue(trader._leave_cooking_to_q_sp6())
        self.assertEqual(2, state["backs"])
        self.assertIn(("info", "料理：按返回后料理列表还在，再按一次返回。"), task.logs)

    def test_it_presses_back_at_most_twice(self):
        trader, task, state = _trader(presses_needed=0)
        self.assertFalse(trader._leave_cooking_to_q_sp6())
        self.assertEqual(2, state["backs"])


class GroupRestoreOffFieldTest(unittest.TestCase):
    def test_no_group_button_is_pressed_off_the_field(self):
        task = _Task()
        trader = object.__new__(Trader)
        trader.task = task
        trader._group_switched = True
        trader._group_before_cooking = 3
        trader._read_skill_group = lambda: self.fail("read off the field")
        trader._restore_skill_group(on_field=False)
        self.assertEqual([], task.clicks)
        self.assertIn(
            ("warning", "料理：没确认回到箱庭，技能组没有切回（原本是第3组），请检查技能栏。"),
            task.logs,
        )


if __name__ == "__main__":
    unittest.main()
