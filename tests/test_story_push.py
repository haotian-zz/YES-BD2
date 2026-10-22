"""主线推图 screens, read live on the bd2 session 2026-10-22 (剧情卡 15, 普通)."""

import unittest
from types import SimpleNamespace

from src.utils import story_push
from src.utils.story_push import StoryScreen


def _box(name, x, y, width=60, height=24):
    return SimpleNamespace(name=name, x=x - width / 2, y=y - height / 2, width=width, height=height)


FIELD_HUD = [
    _box("107,795", 790, 57),
    _box("35,033,668", 960, 57),
    _box("C", 1585, 95),
    _box("M", 206, 246),
    _box("4", 1682, 840),
    _box("SPACE", 1686, 968),
    _box("TAB", 1710, 1048),
]


class ClassifyTest(unittest.TestCase):
    def test_field_with_the_quest_row_presses_the_goal_line(self):
        screen, point = story_push.classify(
            FIELD_HUD + [_box("主线", 1625, 138), _box("前往墙面", 1622, 165)]
        )
        self.assertEqual(StoryScreen.QUEST, screen)
        self.assertEqual((1655, 163), point)

    def test_walking_banner_waits(self):
        screen, point = story_push.classify(
            FIELD_HUD + [_box("主线", 1625, 138), _box("自动移动中：主线任务", 960, 912, 220)]
        )
        self.assertEqual((StoryScreen.WALKING, None), (screen, point))

    def test_talk_presses_the_skip_icon(self):
        screen, point = story_push.classify(
            [_box("使徒布莱德", 800, 315), _box("但其实隐藏着通道。", 950, 352, 400), _box("F1", 1520, 105, 30),
             _box("F2", 1638, 105, 30), _box("F3", 1760, 105, 30)]
        )
        self.assertEqual((StoryScreen.TALK, story_push.TALK_SKIP_POINT), (screen, point))

    def test_skip_dialog_presses_confirm(self):
        screen, point = story_push.classify(
            [_box("跳过对话", 958, 310), _box("主线", 912, 350), _box("取消", 875, 780),
             _box("确认", 1045, 780), _box("ESC", 875, 807), _box("Enter or Space", 1045, 807, 100)]
        )
        self.assertEqual((StoryScreen.SKIP_CONFIRM, (1045, 780)), (screen, point))

    def test_battle_waiting_for_its_first_turn_turns_auto_battle_on(self):
        screen, point = story_push.classify(
            [_box("« TURN.1 »", 960, 105, 140), _box("更换", 124, 1000), _box("预设", 424, 1000),
             _box("TURN.1", 1655, 985), _box("BATTLE", 1767, 985)]
        )
        self.assertEqual((StoryScreen.BATTLE_READY, story_push.AUTO_BATTLE_TOGGLE_POINT), (screen, point))

    def test_auto_battle_waits(self):
        screen, point = story_push.classify(
            [_box("« TURN.1 »", 960, 105, 140), _box("自动战斗中", 140, 940, 120),
             _box("结束自动战斗", 1765, 998, 140), _box("ESC", 1755, 1025, 40)]
        )
        self.assertEqual((StoryScreen.BATTLE_AUTO, None), (screen, point))

    def test_result_presses_leave(self):
        screen, point = story_push.classify(
            [_box("VICTORY", 960, 200, 300), _box("REWARD", 300, 600), _box("离开", 1725, 1008)]
        )
        self.assertEqual((StoryScreen.BATTLE_RESULT, (1725, 1008)), (screen, point))

    def test_arrival_at_a_person_presses_the_interaction_button(self):
        screen, point = story_push.classify(
            FIELD_HUD + [_box("主线", 1625, 138), _box("与拉德尔对话", 1640, 165, 120),
                         _box("F", 930, 351, 20), _box("对话", 1035, 351), _box("F", 1410, 940, 20)]
        )
        self.assertEqual((StoryScreen.INTERACT, story_push.INTERACT_POINT), (screen, point))

    def test_cg_without_text_or_with_a_subtitle_is_clicked_on(self):
        self.assertEqual(StoryScreen.CUTSCENE, story_push.classify([])[0])
        self.assertEqual(StoryScreen.CUTSCENE, story_push.classify([_box("`", 300, 300, 10)])[0])
        screen, point = story_push.classify(
            [_box("使徒布莱德", 960, 870, 120), _box("我是布莱德。喝了蛇怪的阿德林后成为了使徒。", 960, 912, 600)]
        )
        self.assertEqual((StoryScreen.CUTSCENE, story_push.CUTSCENE_POINT), (screen, point))

    def test_field_with_the_quest_row_unread_is_unknown(self):
        self.assertEqual(StoryScreen.UNKNOWN, story_push.classify(FIELD_HUD)[0])

    def test_loading_screen_is_unknown(self):
        screen, _point = story_push.classify([_box("NOW", 1700, 1020), _box("LOADING", 1790, 1020)])
        self.assertEqual(StoryScreen.UNKNOWN, screen)

    def test_first_entry_insert_screen_clicks_the_ring(self):
        screen, point = story_push.classify(
            [_box("Enter or Space", 960, 718, 120), _box("未插好游戏卡。请通过多次点击开始游戏。", 960, 777, 420)]
        )
        self.assertEqual((StoryScreen.INSERT, story_push.INSERT_POINT), (screen, point))

    def test_quest_goal_text(self):
        boxes = FIELD_HUD + [_box("主线", 1625, 138), _box("前往通道另一侧", 1660, 165, 140)]
        self.assertEqual("前往通道另一侧", story_push.quest_goal_text(boxes))
        self.assertEqual("", story_push.quest_goal_text(FIELD_HUD))


if __name__ == "__main__":
    unittest.main()
