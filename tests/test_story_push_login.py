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


class StoryPushStartScreenTest(unittest.TestCase):
    def test_started_on_the_card_collection_is_not_inside_a_card(self):
        task = object.__new__(StoryPushTask)
        task.log_info = lambda *_args, **_kwargs: None
        task.sleep = lambda *_args: None
        title = SimpleNamespace(name="游戏卡珍藏集", x=280, y=30, width=130, height=28)
        task._read_screen = lambda: ([title], {})
        self.assertFalse(task._story_screen_now())


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


class StoryPushDifficultyTest(unittest.TestCase):
    """2026-10-23: a card done on every difficulty (goal 「再次挑战」) is left,
    then a card with a 困难 / 极难 banner is entered; none left ends the run."""

    def _task(self, outcomes, banner_cards):
        task = object.__new__(StoryPushTask)
        task.config = {}
        task._why = ""
        task.log_info = task.info_set = lambda *_args, **_kwargs: None
        task.steps = []
        task._story_screen_now = lambda: True
        task._close_unlock_notices = lambda: None
        task._open_collection = lambda: True
        results = iter(outcomes)
        task._push = lambda _deadline: next(results)
        task._field_to_home = lambda: task.steps.append("home") or True
        task._back_home_from_collection = lambda: task.steps.append("collection home") or True
        task._enter_unfinished_story_card = lambda: task.steps.append("unfinished") or "playing card"
        banners = iter(banner_cards)
        task.skips = []

        def enter_difficulty_card(skip=()):
            task.steps.append("banner")
            task.skips.append(list(skip))
            card = next(banners)
            task._difficulty_pick = None if card == "none" else (0, (100, 200))
            return card

        task._enter_difficulty_card = enter_difficulty_card
        task._after_clear = lambda: None
        return task

    def test_replay_goal_goes_to_a_banner_card_not_back_to_the_card_in_use(self):
        task = self._task(["replay", "replay"], ["card 2", "none"])
        self.assertTrue(task.run_claim())
        self.assertEqual(["home", "banner", "home", "banner", "collection home"], task.steps)

    def test_a_lost_card_is_left_for_the_next_banner_card_once(self):
        task = self._task(["编队打输了 3 次，请先加强编队或换一个阵形预设"] * 2, ["card 13"])
        task.log_warning = lambda *_args, **_kwargs: None
        task._note_why = lambda why: task.steps.append(f"why {why[:5]}")
        task._save_flow_diagnostic = lambda _name: None
        task._claim_fail = lambda label: task.steps.append(f"fail {label}") or False
        self.assertFalse(task.run_claim())
        self.assertEqual(["home", "banner", "why 编队打输了", "fail 推图"], task.steps)

    def test_the_lost_banner_card_is_passed_over_on_the_next_pick(self):
        task = self._task(["编队打输了 3 次，请先加强编队或换一个阵形预设", "replay"], ["card 16", "card 13", "none"])
        task._story_screen_now = lambda: False
        task._enter_unfinished_story_card = lambda: "none"
        task.log_warning = lambda *_args, **_kwargs: None
        self.assertTrue(task.run_claim())
        self.assertEqual([[], [(0, (100, 200))], [(0, (100, 200))]], task.skips)

    def test_replay_goal_is_read_from_the_quest_row(self):
        from src.utils import story_push

        self.assertTrue(story_push.replay_goal("再次挑战主线任务"))
        self.assertFalse(story_push.replay_goal("开始极难难度"))


if __name__ == "__main__":
    unittest.main()
