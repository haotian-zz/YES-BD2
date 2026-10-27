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
        task._enter_unfinished_story_card = lambda _skip=(): task.steps.append("unfinished") or "playing card"
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
        task._enter_unfinished_story_card = lambda _skip=(): "none"
        task.log_warning = lambda *_args, **_kwargs: None
        self.assertTrue(task.run_claim())
        self.assertEqual([[], [(0, (100, 200))], [(0, (100, 200))]], task.skips)

    def test_a_stuck_event_card_is_left_for_the_next_one(self):
        # Summer Knight's 「搬动冰雕」 puzzle, live 2026-10-27.
        task = self._task(["按了主线任务也没有开始自动移动", "cleared"], ["none"])
        task._story_screen_now = lambda: False
        task.log_warning = lambda *_args, **_kwargs: None
        picks = iter([(story_push_task.EVENT_ROW, 0, 350), (story_push_task.EVENT_ROW, 0, 630)])
        task.skips = []

        def enter(skip=()):
            task.skips.append(list(skip))
            pick = next(picks, None)
            task._story_pick = pick
            return "none" if pick is None else "活动游戏卡（没开始的那张）"

        task._enter_unfinished_story_card = enter
        task._enter_difficulty_card = lambda _skip=(): "none"
        self.assertTrue(task.run_claim())
        self.assertEqual(
            [[], [(story_push_task.EVENT_ROW, 0, 350)], [(story_push_task.EVENT_ROW, 0, 350)]],
            task.skips,
        )

    def test_a_stuck_story_card_still_stops_the_run(self):
        task = self._task(["按了主线任务也没有开始自动移动"], [])
        task._story_screen_now = lambda: False
        task._enter_unfinished_story_card = lambda _skip=(): (
            setattr(task, "_story_pick", ("剧情游戏卡", 0, 350)) or "剧情游戏卡（没开始的那张）"
        )
        task._note_why = lambda why: task.steps.append("why")
        task._save_flow_diagnostic = lambda _name: None
        task._claim_fail = lambda label: task.steps.append(f"fail {label}") or False
        self.assertFalse(task.run_claim())
        self.assertEqual(["why", "fail 推图"], task.steps)

    def test_replay_goal_is_read_from_the_quest_row(self):
        from src.utils import story_push

        self.assertTrue(story_push.replay_goal("再次挑战主线任务"))
        self.assertFalse(story_push.replay_goal("开始极难难度"))


class StoryPushRestartedBattleTest(unittest.TestCase):
    """Splash Queen's boss, live 2026-10-27: after the third loss 「返回」 led
    back to the battle's TURN 1, and the run could not get home."""

    def _task(self, boxes):
        task = object.__new__(StoryPushTask)
        task.log_info = task.log_warning = lambda *_args, **_kwargs: None
        task._battle_boxes = lambda: boxes
        task.fled = []
        task.leave_field_battle = lambda label, seen, allowed=False: task.fled.append(allowed) or "left"
        return task

    def test_the_battle_is_run_away_from(self):
        ready = [SimpleNamespace(name="TURN.1", x=1640, y=970, width=50, height=30),
                 SimpleNamespace(name="BATTLE", x=1740, y=970, width=70, height=30)]
        task = self._task(ready)
        task._flee_restarted_battle()
        self.assertEqual([True], task.fled)

    def test_no_battle_is_left_alone(self):
        task = self._task([SimpleNamespace(name="与可疑商人对话", x=1500, y=160, width=200, height=30)])
        task._flee_restarted_battle()
        self.assertEqual([], task.fled)


class StoryPushRowSeekTest(unittest.TestCase):
    """The 活动游戏卡 row is at the foot of the page (live 2026-10-27)."""

    def _task(self, headers):
        task = object.__new__(StoryPushTask)
        task.scrolls = []
        looks = iter(headers)
        task._row_header_y = lambda _titles: next(looks)
        task.scroll_client = lambda _at, notches, **_kwargs: task.scrolls.append(notches)
        return task

    def test_a_row_below_the_screen_is_scrolled_up(self):
        task = self._task([None, None, 1000.0, 738.0])
        self.assertEqual(738.0, task._seek_row(("活动游戏卡",)))
        self.assertEqual([-3, -3, -3], task.scrolls)

    def test_a_row_on_screen_is_read_where_it_is(self):
        task = self._task([180.0])
        self.assertEqual(180.0, task._seek_row(("剧情游戏卡",)))
        self.assertEqual([], task.scrolls)

    def test_a_row_whose_bars_stay_below_the_screen_is_not_used(self):
        task = self._task([900.0, 900.0])
        self.assertIsNone(task._seek_row(("活动游戏卡",)))

    def test_a_missing_row_gives_up(self):
        task = self._task([None] * story_push_task.ROW_SEEK_LOOKS)
        self.assertIsNone(task._seek_row(("活动游戏卡",)))

    def test_a_left_card_is_passed_over_in_its_row(self):
        from src.utils import story_cards

        task = object.__new__(StoryPushTask)
        task.info_set = task.log_info = lambda *_args, **_kwargs: None
        task._reference_frame = lambda: None
        task._drag_row = lambda *_args: None
        cards = [story_cards.StoryCard((350, 810), story_cards.PLAYING), story_cards.StoryCard((630, 810), "not_started")]
        with patch.object(story_cards, "plus_buttons", lambda *_args: [(350, 810), (630, 810)]), patch.object(
            story_cards, "row_cards", lambda *_args: cards
        ):
            self.assertEqual((0, cards[1]), task._first_unfinished_in_row("活动游戏卡", 738.0, [(0, 352)]))
            self.assertEqual((0, cards[0]), task._first_unfinished_in_row("活动游戏卡", 738.0))

    def test_a_row_showing_all_its_owned_cards_is_not_paged(self):
        # 活动游戏卡 5／7, live 2026-10-27: paged, the row slid 160 px and a
        # left card came back at another x and was entered again.
        from src.utils import story_cards

        task = object.__new__(StoryPushTask)
        task.info_set = task.log_info = lambda *_args, **_kwargs: None
        task._reference_frame = lambda: None
        task.drags = []
        task._drag_row = lambda *args: task.drags.append(args)
        full = [story_cards.StoryCard((x, 810), story_cards.FULL) for x in (345, 625, 905, 1185, 1465)]
        with patch.object(story_cards, "plus_buttons", lambda *_args: [card.plus for card in full]), patch.object(
            story_cards, "row_cards", lambda *_args: full
        ):
            self.assertIsNone(task._first_unfinished_in_row("活动游戏卡", 738.0, (), owned=5))
        self.assertEqual(1, len(task.drags))  # only the drag back to the row's start

    def test_the_owned_count_is_read_from_the_header(self):
        from src.utils import story_cards

        self.assertEqual(5, story_cards.owned_count(SimpleNamespace(name="活动游戏卡 5／7")))
        self.assertEqual(15, story_cards.owned_count(SimpleNamespace(name="剧情游戏卡15/20")))
        self.assertIsNone(story_cards.owned_count(SimpleNamespace(name="活动游戏卡")))


if __name__ == "__main__":
    unittest.main()
