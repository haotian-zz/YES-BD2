import itertools
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.tasks import StoryPushTask as story_push_task
from src.tasks.StoryPushTask import StoryPushTask


class StoryPushLoginTest(unittest.TestCase):
    """Started on the title screen, the push logs in itself (live 2026-10-22)."""

    def _task(self, opens, login):
        task = object.__new__(StoryPushTask)
        task._why = ""
        task.log_info = lambda *_args, **_kwargs: None
        task.sleep = lambda _seconds: None
        results = iter(opens)

        def open_page(*_args):
            ok, title = next(results)
            task._recovery_saw_title = title
            task._why = "" if ok else (task._why or "不在主页")
            return ok

        task._open_page_from_home = open_page
        task._executor = SimpleNamespace(get_task_by_class=lambda _cls: login)
        return task

    def test_title_screen_logs_in_then_opens_the_collection(self):
        ticks = []
        login = SimpleNamespace(_enabled=True, _finished=False)
        login.run = lambda: ticks.append(1) or (len(ticks) == 3 and setattr(login, "_finished", True))
        task = self._task([(False, True), (True, False)], login)
        self.assertTrue(task._open_collection())
        self.assertEqual(3, len(ticks))

    def test_no_title_screen_does_not_log_in(self):
        login = SimpleNamespace(_enabled=True, _finished=False, run=lambda: self.fail("logged in"))
        task = self._task([(False, False)], login)
        self.assertFalse(task._open_collection())

    def test_auto_login_off_says_so(self):
        login = SimpleNamespace(_enabled=False, _finished=False)
        task = self._task([(False, True)], login)
        self.assertFalse(task._open_collection())
        self.assertIn("自动登录没开", task._why)


class StoryPushProgressTest(unittest.TestCase):
    def test_two_screens_in_turn_stop_as_no_progress(self):
        # card 18 live 2026-10-22: a bystander's F button and its close-up, in turn.
        task = object.__new__(StoryPushTask)
        task.config = {}
        task.info_set = task.log_info = task.log_warning = lambda *_args, **_kwargs: None
        task.sleep = task.tap_key = task._click_reference = lambda *_args, **_kwargs: None
        looks = itertools.cycle([{"interact": True}, {"npc_focus": True}])
        task._read_screen = lambda: ([], next(looks))
        clock = itertools.count(0, 10)
        with patch.object(story_push_task, "monotonic", lambda: next(clock)):
            why = task._push(deadline=10**9)
        self.assertIn("分钟没有推进", why)


if __name__ == "__main__":
    unittest.main()
