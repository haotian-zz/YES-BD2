import unittest
from types import SimpleNamespace

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


if __name__ == "__main__":
    unittest.main()
