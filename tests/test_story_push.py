"""主线推图 screens, read live on the bd2 session 2026-10-22 (剧情卡 15, 普通)."""

import unittest
from types import SimpleNamespace

import cv2
import numpy as np

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

    def test_a_done_step_row_reads_like_the_quest_row(self):
        # card 18 live 2026-10-22: 「完成」 over 「返回艾达与拉德尔所…」, a child's
        # thought bubble nearby (F) pressed for a minute instead.
        boxes = FIELD_HUD + [_box("完成", 1608, 135), _box("+", 1824, 150, 20), _box("返回艾达与拉德尔所", 1678, 164, 200)]
        self.assertEqual((StoryScreen.QUEST, (1638, 160)), story_push.classify(boxes))
        self.assertEqual((1638, 160), story_push.quest_point(boxes + [_box("F", 1410, 940, 20)]))
        self.assertEqual("返回艾达与拉德尔所", story_push.quest_goal_text(boxes))

    def test_hard_difficulty_start_presses_accept(self):
        # card 1 live 2026-10-23: 「开始困难难度」 opened the 困难难度 box over the
        # field HUD; it sat as unknown until stopped.
        boxes = FIELD_HUD + [
            _box("主线", 1625, 138),
            _box("开始困难难度", 1640, 164, 140),
            _box("困难难度", 960, 328, 120),
            _box("难度仅适用于主线任务战斗。是否开始主线任务？", 960, 375, 500),
            _box("取消", 870, 752),
            _box("领取探索", 1047, 752, 90),
        ]
        self.assertEqual((StoryScreen.ACCEPT, (1047, 752)), story_push.classify(boxes))

    def test_lone_answer_mid_screen_is_taken(self):
        # card 1 困难 live 2026-10-23: 「1 呃…怎么了…？」 framed mid-screen over
        # black; 跳过 did nothing for five minutes.
        boxes = [_box("Q", 1758, 59, 20), _box("F", 1520, 104, 20), _box("F2", 1640, 104, 30),
                 _box("呃…怎么了…？", 951, 537, 180)]
        self.assertEqual((StoryScreen.CHOICE, (951, 537)), story_push.classify(boxes))

    def test_quick_exploration_offer_page_and_rewards(self):
        # card 2 困难 live 2026-10-23
        offer = [_box("进行快速探索", 960, 450, 180), _box("困难难度", 960, 492, 100),
                 _box("取消", 832, 635), _box("立刻前往", 1086, 635, 90)]
        self.assertEqual((StoryScreen.ACCEPT, (1086, 635)), story_push.classify(offer))
        page = [_box("恶魔的傲骨-困难", 410, 50, 220), _box("当前战斗力49398", 1308, 47, 160),
                _box("9.返回休息室", 311, 148, 140), _box("可获得奖励", 1249, 801, 120),
                _box("前往当前探索", 252, 1006, 140)]
        self.assertEqual((StoryScreen.QUICK_EXPLORE, (1660, 1006)),
                         story_push.classify(page + [_box("自动进行", 1660, 1006, 100)]))
        self.assertEqual((StoryScreen.QUICK_EXPLORE, (1658, 1004)),
                         story_push.classify(page + [_box("战斗", 1658, 1004, 50)]))
        reward = page + [_box("REWARD", 958, 334, 120), _box("获得1种", 959, 382, 80),
                         _box("点击画面即可返回。", 953, 988, 180), _box("自动进行", 1660, 1006, 100)]
        self.assertEqual((StoryScreen.QUICK_REWARD, story_push.QUICK_REWARD_POINT), story_push.classify(reward))

    def test_replay_dialog_is_cancelled(self):
        # card 2 after 极难 live 2026-10-23: the goal line was not read.
        boxes = FIELD_HUD + [_box("再次挑战任务", 960, 362, 160), _box("普通难度", 960, 436, 100),
                             _box("可以再次挑战已通关的主线任务。", 960, 505, 300),
                             _box("取消", 832, 729), _box("同意", 1086, 729)]
        self.assertEqual((StoryScreen.REPLAY, (832, 729)), story_push.classify(boxes))

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

    def test_talk_with_options_takes_the_first(self):
        screen, point = story_push.classify(
            [_box("F", 1520, 101, 20), _box("F2", 1639, 104, 30), _box("F3", 1761, 104, 30),
             _box("起床。", 951, 905), _box("重新躺下。", 951, 991, 100)]
        )
        self.assertEqual((StoryScreen.CHOICE, (951, 905)), (screen, point))

    def test_skip_dialog_presses_confirm(self):
        screen, point = story_push.classify(
            [_box("跳过对话", 958, 310), _box("主线", 912, 350), _box("取消", 875, 780),
             _box("确认", 1045, 780), _box("ESC", 875, 807), _box("Enter or Space", 1045, 807, 100)]
        )
        self.assertEqual((StoryScreen.SKIP_CONFIRM, (1045, 780)), (screen, point))

    def test_skip_dialog_over_a_battle_talk_sits_higher(self):
        screen, point = story_push.classify(
            [_box("跳过对话", 958, 460), _box("跳过对话。", 958, 513), _box("可于剧情菜单重新查看。", 958, 550, 240),
             _box("取消", 874, 628), _box("确认", 1044, 628), _box("悠丝缇亚", 340, 930)]
        )
        self.assertEqual((StoryScreen.SKIP_CONFIRM, (1044, 628)), (screen, point))

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

    def test_defeat_retries_then_goes_back(self):
        boxes = [_box("DEFEAT", 958, 273, 200), _box("第1次", 1150, 941), _box("返回", 778, 993),
                 _box("重新挑战", 968, 993, 100), _box("继续", 1159, 992)]
        self.assertEqual((StoryScreen.BATTLE_DEFEAT, (968, 993)), story_push.classify(boxes))
        self.assertEqual((778, 993), story_push.defeat_back_point(boxes))
        confirm = boxes + [_box("重新挑战", 960, 405, 100), _box("是否重新挑战？", 960, 532, 140),
                           _box("取消", 770, 686), _box("从上一回合开始", 970, 686, 140),
                           _box("从最初开始", 1169, 686, 100)]
        self.assertEqual((StoryScreen.RETRY_CONFIRM, (1169, 686)), story_push.classify(confirm))

    def test_preset_is_used_and_confirmed(self):
        ready = [_box("TURN.1", 1663, 985), _box("BATTLE", 1772, 985), _box("更换", 122, 1002),
                 _box("预设", 422, 1002), _box("推荐部署", 522, 1002, 100)]
        self.assertEqual((422, 1002), story_push.preset_button_point(ready))
        self.assertIsNone(story_push.preset_use_point(ready))
        panel = ready + [_box("全部删除", 445, 275, 100), _box("阵形预设", 960, 276, 100),
                         _box("无名称", 491, 350), _box("删除", 1229, 476), _box("使用", 1356, 476),
                         _box("覆盖", 1481, 476), _box("删除", 1229, 691), _box("使用", 1355, 692),
                         _box("覆盖", 1481, 692), _box("最近使用阵形", 1260, 812, 120)]
        self.assertEqual((1356, 476), story_push.preset_use_point(panel))
        self.assertEqual((StoryScreen.PRESET_PANEL, story_push.PRESET_PANEL_CLOSE_POINT), story_push.classify(panel))
        self.assertEqual((1355, 692), story_push.preset_use_point(panel, 2))
        self.assertIsNone(story_push.preset_use_point(panel, 3))
        confirm = [_box("使用预设", 453, 273, 100), _box("是否使用无名称预设？使用预设时，装备也将一同", 1282, 711, 400),
                   _box("取消", 1178, 812), _box("确认", 1388, 811)]
        self.assertEqual((1388, 811), story_push.preset_confirm_point(confirm))
        self.assertEqual((StoryScreen.PRESET_CONFIRM, (1388, 811)), story_push.classify(confirm))
        self.assertIsNone(story_push.preset_confirm_point(panel))

    def test_arrival_at_a_person_presses_the_interaction_button(self):
        screen, point = story_push.classify(
            FIELD_HUD + [_box("主线", 1625, 138), _box("与拉德尔对话", 1640, 165, 120),
                         _box("F", 930, 351, 20), _box("对话", 1035, 351), _box("F", 1410, 940, 20)]
        )
        self.assertEqual((StoryScreen.INTERACT, story_push.INTERACT_POINT), (screen, point))

    def test_walking_past_a_person_does_not_talk_to_them(self):
        boxes = FIELD_HUD + [_box("主线", 1625, 138), _box("自动移动中：主线任务", 960, 912, 220)]
        self.assertEqual(StoryScreen.WALKING, story_push.classify(boxes, {"interact": True})[0])

    def test_npc_focus_goes_back(self):
        boxes = [_box("科库托斯工学家", 963, 286, 140), _box("创造性产物·", 937, 320, 120), _box("F1", 1724, 908, 30)]
        self.assertEqual(
            (StoryScreen.NPC_FOCUS, story_push.NPC_FOCUS_BACK_POINT), story_push.classify(boxes, {"npc_focus": True})
        )

    def test_quest_point(self):
        self.assertEqual((1655, 163), story_push.quest_point(FIELD_HUD + [_box("主线", 1625, 138)]))
        self.assertIsNone(story_push.quest_point(FIELD_HUD))

    def test_cg_without_text_or_with_a_subtitle_is_clicked_on(self):
        self.assertEqual(StoryScreen.CUTSCENE, story_push.classify([])[0])
        self.assertEqual(StoryScreen.CUTSCENE, story_push.classify([_box("`", 300, 300, 10)])[0])
        screen, point = story_push.classify(
            [_box("使徒布莱德", 960, 870, 120), _box("我是布莱德。喝了蛇怪的阿德林后成为了使徒。", 960, 912, 600)]
        )
        self.assertEqual((StoryScreen.CUTSCENE, story_push.CUTSCENE_POINT), (screen, point))

    def test_field_hud_alone_is_never_a_cg(self):
        self.assertEqual(StoryScreen.UNKNOWN, story_push.classify([_box("SPACE", 1686, 968), _box("TAB", 1710, 1048)])[0])

    def test_battle_role_dialog_is_cancelled(self):
        screen, point = story_push.classify(
            FIELD_HUD + [_box("战场角色设置", 420, 293, 160), _box("剧情角色阵形", 435, 356, 140),
                         _box("当前战斗阵形", 640, 356, 140), _box("取消", 1158, 811), _box("确认", 1428, 811)]
        )
        self.assertEqual((StoryScreen.DIALOG, (1158, 811)), (screen, point))

    def test_field_with_the_quest_row_unread_is_unknown(self):
        self.assertEqual(StoryScreen.UNKNOWN, story_push.classify(FIELD_HUD)[0])

    def test_loading_screen_is_unknown(self):
        screen, _point = story_push.classify([_box("NOW", 1700, 1020), _box("LOADING", 1790, 1020)])
        self.assertEqual(StoryScreen.UNKNOWN, screen)

    def test_difficulty_played_through(self):
        screen, point = story_push.classify(
            [_box("完成主线任务普通", 1280, 392, 240), _box("已完成普通难度的所有探索。", 1270, 426, 260),
             _box("10,000", 1257, 632), _box("100", 1386, 632)]
        )
        self.assertEqual((StoryScreen.CLEARED, story_push.CLEARED_POINT), (screen, point))

    def test_guide_book_after_the_clear_opens_the_collection(self):
        screen, point = story_push.classify(
            [_box("指南", 793, 218), _box("恶魔的傲骨", 803, 290, 140), _box("普通", 760, 398), _box("完成", 760, 422),
             _box("困难", 760, 462), _box("可进行", 768, 486), _box("前往游戏卡珍藏集", 1648, 990, 200),
             _box("SPACE OR ENTER", 1648, 1029, 100)]
        )
        self.assertEqual((StoryScreen.GUIDE, (1648, 990)), (screen, point))

    def test_unlock_notice_on_home(self):
        boxes = [_box("主线任务解锁", 390, 463, 180), _box("「恶魔的傲骨」游戏卡主线任务的困难难度开启。", 390, 563, 440),
                 _box("移动", 400, 684), _box("抽抽乐", 160, 1020)]
        self.assertTrue(story_push.unlock_notice(boxes))
        self.assertFalse(story_push.unlock_notice(FIELD_HUD))

    def test_home_is_never_a_cg(self):
        boxes = [_box("抽抽乐", 160, 1020), _box("角色", 266, 1020), _box("付费商店", 1117, 1020, 100)]
        self.assertEqual((StoryScreen.HOME, None), story_push.classify(boxes))
        self.assertEqual((StoryScreen.HOME, None), story_push.classify(boxes[:1]))

    def test_first_entry_insert_screen_clicks_the_ring(self):
        screen, point = story_push.classify(
            [_box("Enter or Space", 960, 718, 120), _box("未插好游戏卡。请通过多次点击开始游戏。", 960, 777, 420)]
        )
        self.assertEqual((StoryScreen.INSERT, story_push.INSERT_POINT), (screen, point))

    def test_talk_found_by_its_skip_icon_when_the_labels_misread(self):
        # The game's OCR read 「F1 F2 F3」 as 「日 y 因」 (live 2026-10-22).
        boxes = [_box("1)", 1281, 58, 20), _box("y", 1640, 60, 20), _box("日", 1520, 101, 20),
                 _box("因", 1760, 103, 20), _box("1", 655, 904, 20), _box("起床。", 951, 905),
                 _box("0", 656, 992, 20), _box("重新躺下。", 950, 990, 100)]
        self.assertEqual(StoryScreen.UNKNOWN, story_push.classify(boxes)[0])
        self.assertEqual((StoryScreen.CHOICE, (951, 905)), story_push.classify(boxes, {"talk_skip": True}))
        lone = [_box("日", 1520, 101, 20), _box("y", 1640, 60, 20), _box("因", 1760, 103, 20)]
        self.assertEqual(StoryScreen.TALK, story_push.classify(lone, {"talk_skip": True})[0])

    def test_icons_are_found_in_their_corner(self):
        frame = np.zeros((1080, 1920, 3), np.uint8)
        self.assertEqual({"talk_skip": False, "interact": False, "npc_focus": False}, story_push.icons(frame))
        for path, (x, y) in (
            (story_push.TALK_SKIP_TEMPLATE, (1615, 35)),
            (story_push.INTERACT_TEMPLATE, (1383, 858)),
            (story_push.NPC_FOCUS_TEMPLATE, (1697, 812)),
        ):
            template = cv2.imread(str(path))
            frame[y : y + template.shape[0], x : x + template.shape[1]] = template
        self.assertEqual({"talk_skip": True, "interact": True, "npc_focus": True}, story_push.icons(frame))

    def test_quest_goal_text(self):
        boxes = FIELD_HUD + [_box("主线", 1625, 138), _box("前往通道另一侧", 1660, 165, 140)]
        self.assertEqual("前往通道另一侧", story_push.quest_goal_text(boxes))
        self.assertEqual("", story_push.quest_goal_text(FIELD_HUD))
        doubled = FIELD_HUD + [_box("主线", 1625, 138), _box("进入门内", 1640, 165, 80), _box("进入门", 1730, 165, 60)]
        self.assertEqual("进入门内", story_push.quest_goal_text(doubled))
        self.assertTrue(story_push.same_goal("日进入门内进入门内", "进入门内"))
        self.assertFalse(story_push.same_goal("前往传输装置", "进入门内"))
        self.assertTrue(story_push.same_goal("日兰身边逃开 从兰身", "从兰身边逃开"))
        self.assertFalse(story_push.same_goal("返回餐厅地下", "前往餐厅一楼"))
        self.assertFalse(story_push.same_goal("打倒兰", "与兰对话"))
        self.assertFalse(story_push.same_goal("进入门内", ""))


if __name__ == "__main__":
    unittest.main()
