"""主线推图: play the first unfinished story cartridge on 普通 by itself.

Flow from the user (2026-10-22): 主页 → P (or the cartridge slot bottom
right) → 游戏卡珍藏集 → the first 剧情游戏卡 whose white progress bar is not
full → its field → press the top-right 主线 row (or E) and the party walks to
the next point by itself; battles use the default formation on the game's
auto battle, talks are skipped.  「持续推进」 goes on with the next
unfinished cartridge.

What each screen asks for is ``src.utils.story_push.classify``.  Progress
is a change of screen kind or of the 主线 goal line; none for
「无进展停止分钟」 stops the run with what was on screen (a puzzle the walk
cannot solve, a battle the default formation loses), per the 2game-helper
test rule 「长时间无法推进时停下来一起分析原因」.
"""

from __future__ import annotations

from collections import deque
from time import monotonic

import cv2
from qfluentwidgets import FluentIcon

from src.tasks.BaseBD2Task import KEY_TAP_SECONDS
from src.tasks.DoomBookTask import (
    CARTRIDGE_SLOT_POINT,
    COLLECTION_TITLE_KEYWORDS,
    CartridgeFieldTask,
)
from src.tasks.task_vision_mixin import REFERENCE_HEIGHT, REFERENCE_WIDTH
from src.utils import story_cards, story_push
from src.utils.story_push import StoryScreen

# Rows in the order the user gave (2026-10-22): 剧情游戏卡 first, then 店长.
ROWS = (("剧情游戏卡", story_cards.STORY_ROW_TITLES), ("店长游戏卡", story_cards.MASTER_ROW_TITLES))
PAGE_SCROLL_UP_NOTCHES = 10
# A row is dragged on its cards' art (header + 150), five cards at a time.
ROW_DRAG_BELOW_HEADER = 150
ROW_DRAG_LEFT_X, ROW_DRAG_RIGHT_X = 300, 1700
ROW_DRAG_SECONDS = 0.8
ROW_DRAGS_MAX = 6
# Read at full size: the default whole-frame read shrinks to 720 lines and
# lost the talk's small 「F2」 label (live 2026-10-22).
FULL_SCREEN = (0, 0, REFERENCE_WIDTH, REFERENCE_HEIGHT)

LABEL = "主线推图"
CONTINUE_KEY = "持续推进"
# The user (2026-10-22): the formation (and the order its characters act in)
# drifted after a while and battles were lost.  It carries over between
# battles, so a preset is used only for the 重新挑战 after a loss: 「先默认第一个」,
# and the number can be set.
PRESET_KEY = "战败重试时套用的预设"
PRESET_LOOKS = 3
NO_PROGRESS_KEY = "无进展停止分钟"
MAX_MINUTES_KEY = "最长运行分钟"
NO_PROGRESS_MINUTES = 5
# A screen seen among the last this many (same goal) is no progress.
RECENT_SCREENS = 4
MAX_MINUTES = 180
# Quest-row presses on one goal without the walk starting before E is tried,
# and E presses after that before the run stops.
QUEST_PRESSES_BEFORE_KEY = 3
QUEST_KEY_PRESSES = 2
# Auto-battle toggle presses on one battle before 「BATTLE」 is pressed instead.
AUTO_TOGGLE_PRESSES = 3
# 跳过 presses on one talk before its line is clicked on instead.
TALK_SKIP_PRESSES = 2
# Lost battles in one cartridge before the run stops: 重新挑战 twice, then stop
# (the user 2026-10-22 「重新挑战几次再停」).
DEFEATS_MAX = 3
DEFEAT_SETTLE_SECONDS = 2.0
DEFEAT_WORDS = ("defeat",)
# The field HUD (SPACE / TAB under the skill wheel) with the quest row unread:
# E after this long.
FIELD_ONLY_KEY_SECONDS = 4.0
POLL_SECONDS = 1.0
# Login (with a data download after an update) before the push gives up.
LOGIN_MAX_SECONDS = 900
# A clear is followed by the next story, the 「指南」 book or the field
# within this many looks (about 2 s each).
AFTER_CLEARED_LOOKS = 10
UNLOCK_CLOSE_MAX = 4
# Returns to 主页 in mid-push before the run stops.
HOME_RETURNS_MAX = 2
# F presses when the goal row starts no walk (the goal is right here).
INTERACT_KEY_PRESSES = 2
# Goal presses before the interaction button is taken (see _push).
INTERACT_QUEST_FIRST = 1
# A walk can stall behind a jar on a ledge, the banner still up (card 15,
# live 2026-10-22); stopped and pressed again after this long, it went on.
WALK_REPATH_SECONDS = 45.0
STORY_GOES_ON = (
    StoryScreen.INSERT,
    StoryScreen.SKIP_CONFIRM,
    StoryScreen.CHOICE,
    StoryScreen.TALK,
    StoryScreen.BATTLE_AUTO,
    StoryScreen.BATTLE_RESULT,
    StoryScreen.BATTLE_DEFEAT,
    StoryScreen.RETRY_CONFIRM,
    StoryScreen.BATTLE_READY,
    StoryScreen.WALKING,
    StoryScreen.QUEST,
    StoryScreen.CUTSCENE,
)


class StoryPushTask(CartridgeFieldTask):
    claim_log_name = "story_push"
    label = LABEL
    # Started inside a story cartridge (the user: 「如果已经选择了一个剧情游戏卡
    # 那就直接进入这个游戏卡开始推图」), a cut-scene cannot be left for 主页
    # (Esc / H / back do nothing there, live 2026-10-22): run_claim decides.
    start_from_home = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = LABEL
        self.description = (
            "主页卡带 → 游戏卡珍藏集 → 第一张进度条没满的剧情游戏卡 → 点右上角主线自动移动，"
            "剧情跳过、战斗用当前编队自动战斗（输了套用阵形预设再重新挑战），一直推到这张卡打完。"
        )
        self.icon = FluentIcon.PLAY
        self.group_name = "推图"
        self.default_config[CONTINUE_KEY] = True
        self.default_config[PRESET_KEY] = 1
        self.default_config[NO_PROGRESS_KEY] = NO_PROGRESS_MINUTES
        self.default_config[MAX_MINUTES_KEY] = MAX_MINUTES
        self.config_description[CONTINUE_KEY] = "一张剧情游戏卡打完后，接着推下一张没打完的。"
        self.config_description[PRESET_KEY] = (
            "战斗输了重新挑战时，先点「预设」套用阵形预设里第几个编队（连同装备，从上往下数，"
            "只认面板上不用滚动就看得到的）；0 表示不套用。"
        )
        self.config_description[NO_PROGRESS_KEY] = (
            "这么多分钟画面一直没有推进（例如解谜关、默认编队打不过）就停下，并说明停在哪里。"
        )
        self.config_description[MAX_MINUTES_KEY] = "整次推图最多跑这么多分钟。"

    # -- entry --------------------------------------------------------------------

    def run_claim(self) -> bool:
        deadline = monotonic() + 60 * max(1, int(self.config.get(MAX_MINUTES_KEY, MAX_MINUTES)))
        cleared = home_returns = 0
        inside = self._story_screen_now()
        while True:
            if inside:
                inside = False
                card = "当前的剧情游戏卡"
                if not cleared:
                    self.log_info(f"{LABEL}：已经在剧情游戏卡里，直接推图。")
            else:
                self._close_unlock_notices()
                if not self._open_collection():
                    return self._claim_fail("打开游戏卡珍藏集")
                card = self._enter_unfinished_story_card()
                if card is None:
                    return self._claim_fail("进入剧情游戏卡")
                if card == "none":
                    self.log_info(f"{LABEL}：剧情游戏卡都已推完。")
                    return self._back_home_from_collection()
            outcome = self._push(deadline)
            if outcome == "home" and home_returns < HOME_RETURNS_MAX:
                home_returns += 1
                self.log_info(f"{LABEL}：推图中回到了主页，重新选卡。")
                continue
            if outcome != "cleared":
                self._note_why(outcome)
                self._save_flow_diagnostic("story_push_stopped")
                return self._claim_fail("推图")
            cleared += 1
            self.log_info(f"{LABEL}：{card}已推完（本次第 {cleared} 张）。")
            # What follows a clear differs (live 2026-10-22): the prologue (卡 1)
            # goes straight on into the next story's talks and CGs, pushed where
            # it plays; WAY OF THE DEMON opens its 「指南」 book, whose
            # 「前往游戏卡珍藏集」 leads to the next card; else the played
            # card's field is left for 主页.
            after = self._after_clear()
            go_on = bool(self.config.get(CONTINUE_KEY, True)) and monotonic() < deadline
            if after == StoryScreen.GUIDE:
                if not go_on and self.config.get(CONTINUE_KEY, True):
                    # Left for 主页 only when going on.
                    self._close_unlock_notices()
                    return self._wait_for_home_confirmation(f"{LABEL}返回主页", timeout=10.0)
                if not go_on:
                    return True
                continue
            if after is not None:
                if not go_on:
                    return True
                self.log_info(f"{LABEL}：推完后游戏直接接着播下一段剧情，继续推。")
                inside = True
                continue
            if not go_on:
                return self._field_to_home()
            if not self._field_to_home():
                return self._claim_fail("返回主页")

    def _open_collection(self) -> bool:
        """游戏卡珍藏集 from 主页, logging in first when the game is on its
        title screen (started right after the game opened, or sent back there
        mid-push)."""
        for _attempt in range(2):
            self._recovery_saw_title = False
            if self._open_page_from_home("游戏卡珍藏集", CARTRIDGE_SLOT_POINT, COLLECTION_TITLE_KEYWORDS):
                return True
            if not getattr(self, "_recovery_saw_title", False) or not self._log_in_here():
                return False
        return False

    def _log_in_here(self) -> bool:
        """Run the auto-login step here until it reaches 主页.

        A task started by itself runs as ok-script's one-time task, and the
        login trigger does not run while one does (live 2026-10-22: started
        on 「TOUCH TO START」, the push stopped at once with 「交给自动登录」).
        """
        try:
            from src.tasks.trigger.AutoLoginTask import AutoLoginTask
        except ImportError:  # pragma: no cover
            return False
        self._why = ""  # 「没能回到主页」 was the title screen
        login = self.executor.get_task_by_class(AutoLoginTask)
        if login is None or not bool(getattr(login, "_enabled", False)):
            self._note_why("游戏在标题画面，自动登录没开，请先登录")
            return False
        self.log_info(f"{LABEL}：游戏在标题画面，先自动登录。")
        deadline = monotonic() + LOGIN_MAX_SECONDS
        while monotonic() < deadline:
            if getattr(login, "_finished", False):
                self.log_info(f"{LABEL}：自动登录完成，接着推图。")
                return True
            login.run()
            self.sleep(POLL_SECONDS)
        self._note_why(f"自动登录 {LOGIN_MAX_SECONDS // 60} 分钟还没到主页")
        return False

    def _after_clear(self) -> StoryScreen | None:
        """GUIDE once its button opened the collection, another story screen
        when the story plays on, None for the played card's field."""
        cleared_shown = 0
        for _look in range(AFTER_CLEARED_LOOKS):
            boxes, seen = self._read_screen()
            screen, point = story_push.classify(boxes, seen)
            if screen == StoryScreen.CLEARED:
                # Still up after its click: Space, then a click again.
                cleared_shown += 1
                self.log_info(f"{LABEL}：完成画面还在，再关一次。")
                if cleared_shown % 2 and self._send_game_key(story_push.CLEARED_KEY_CODE, KEY_TAP_SECONDS):
                    self.sleep(2.0)
                else:
                    self._click_reference(*point, after_sleep=2.0)  # 不用确认：下一轮重看完成画面还在不在
                continue
            if screen == StoryScreen.GUIDE:
                if not self.config.get(CONTINUE_KEY, True):
                    return screen
                # The button lands on 主页 (live 2026-10-22), not the collection.
                self.log_info(f"{LABEL}：指南页点「前往游戏卡珍藏集」。")
                self._click_reference(*point, after_sleep=2.0)  # 不用确认：接着由回主页、开珍藏集流程确认
                return screen
            if screen in STORY_GOES_ON:
                return screen
            self.sleep(POLL_SECONDS)
        return None

    def _close_unlock_notices(self) -> None:
        """✕ the 「主线任务解锁」 cards 主页 shows after a clear."""
        for _look in range(UNLOCK_CLOSE_MAX):
            boxes = self._reference_boxes(self.capture_frame(), FULL_SCREEN, LABEL)
            if not story_push.unlock_notice(boxes):
                return
            self.log_info(f"{LABEL}：关掉「主线任务解锁」提示。")
            self._click_reference(*story_push.UNLOCK_CLOSE_POINT, after_sleep=1.5)  # 不用确认：下一轮重看提示还在不在

    def clear_temporary_home_announcement_if_needed(self, **signals) -> bool:
        """The 「主线任务解锁」 card a clear leaves on 主页 dims it like a login
        announcement, but only its ✕ closes it (live 2026-10-22: the
        announcement spot under it was clicked for a minute)."""
        if signals.get("brightness", 0.0) < signals.get("brightness_threshold", 0.0):
            boxes = self._reference_boxes(self.capture_frame(), FULL_SCREEN, LABEL)
            if story_push.unlock_notice(boxes):
                self.log_info(f"{LABEL}：关掉「主线任务解锁」提示。")
                self._click_reference(*story_push.UNLOCK_CLOSE_POINT, after_sleep=1.5)  # 不用确认：主页确认流程下一轮重看
                return True
        return super().clear_temporary_home_announcement_if_needed(**signals)

    def _leave_defeat(self, boxes) -> None:
        """「返回」 out of the defeat screen (no dialog; it goes on with the
        story's talk), pressed again while the screen still animates in."""
        for _look in range(PRESET_LOOKS):
            self.sleep(DEFEAT_SETTLE_SECONDS)
            self._click_reference(*story_push.defeat_back_point(boxes), after_sleep=2.0)  # 不用确认：下面重看战败画面还在不在
            boxes, seen = self._read_screen()
            if story_push.classify(boxes, seen)[0] != StoryScreen.BATTLE_DEFEAT:
                return
        self.log_warning(f"{LABEL}：战败画面的「返回」没点掉。")

    def _apply_preset(self, boxes, number: int) -> bool:
        """「预设」 → row ``number``'s 「使用」 → 确认, back on the battle's first turn."""
        self.log_info(f"{LABEL}：重新挑战前套用第 {number} 个阵形预设。")
        self._click_reference(*story_push.preset_button_point(boxes), after_sleep=1.5)  # 不用确认：下面重看阵形预设面板
        use_point = None
        for _look in range(PRESET_LOOKS):
            panel = self._reference_boxes(self.capture_frame(), FULL_SCREEN, LABEL)
            use_point = story_push.preset_use_point(panel, number)
            if use_point is not None or story_push.preset_panel_shown(panel):
                break
            self.sleep(POLL_SECONDS)
        if use_point is None:
            self.log_warning(f"{LABEL}：阵形预设面板上没找到第 {number} 个预设，按当前编队开打。")
            if story_push.preset_panel_shown(panel):
                self._click_reference(*story_push.PRESET_PANEL_CLOSE_POINT, after_sleep=1.0)  # 不用确认：推图循环下一轮重看画面
            return False
        self._click_reference(*use_point, after_sleep=1.5)  # 不用确认：下面重看「使用预设」确认框
        # 确认 does nothing while the dialog still slides in (live 2026-10-22):
        # pressed until the dialog is gone.
        pressed = False
        for _look in range(PRESET_LOOKS * 2):
            now = self._reference_boxes(self.capture_frame(), FULL_SCREEN, LABEL)
            confirm = story_push.preset_confirm_point(now)
            if confirm is None and pressed:
                return True
            if confirm is not None:
                pressed = True
                self._click_reference(*confirm, after_sleep=2.0)  # 不用确认：下一轮重看确认框还在不在
            elif story_push.preset_panel_shown(now):
                self._click_reference(*use_point, after_sleep=1.5)  # 不用确认：下一轮重看确认框出没出来
            else:
                self.sleep(POLL_SECONDS)
        self.log_warning(f"{LABEL}：「使用预设」确认框没点掉，按当前编队开打。")
        return False

    def _story_screen_now(self) -> bool:
        """Two reads in a row show a story screen (talk, CG, battle, field)."""
        for look in range(2):
            if look:
                self.sleep(0.8)
            boxes, seen = self._read_screen()
            screen, _point = story_push.classify(boxes, seen)
            if screen == StoryScreen.HOME or (screen == StoryScreen.UNKNOWN and not self._field_hud_shown(boxes)):
                self.log_info(
                    f"{LABEL}：开始时不在剧情画面，读到 "
                    + " | ".join(f"{box.name}@{box.x + box.width / 2:.0f},{box.y + box.height / 2:.0f}" for box in boxes)
                )
                return False
        return True

    # -- cartridge choice ------------------------------------------------------------

    def _enter_unfinished_story_card(self) -> str | None:
        """Enter the first story card whose bar is not full.

        Returns the card's label, "none" when every story card is done, None
        when it could not be entered.
        """
        # The page opens scrolled to the card in use; the top rows first.
        self.scroll_client((0.5, 0.55), PAGE_SCROLL_UP_NOTCHES, count=1, after_sleep=1.0)
        rows_seen = 0
        for row_name, titles in ROWS:
            header_y = self._row_header_y(titles)
            if header_y is None:
                self.log_info(f"{LABEL}：游戏卡珍藏集里没看到「{row_name}」这一排。")
                continue
            rows_seen += 1
            card = self._first_unfinished_in_row(row_name, header_y)
            if card is None:
                continue
            label = f"{row_name}（{'推到一半' if card.bar == story_cards.PLAYING else '没开始'}的那张）"
            self.log_info(f"{LABEL}：进入{label}。")
            self._click_reference(*card.click_point, after_sleep=2.0)  # 不用确认：推图循环接着看画面
            return label
        if not rows_seen:
            self._note_why("游戏卡珍藏集里一排剧情游戏卡都没看到")
            return None
        self._save_flow_diagnostic("story_cards_all_full")
        return "none"

    def _row_header_y(self, titles) -> float | None:
        boxes = self._reference_boxes(self.capture_frame(), None, "珍藏集行标题")
        box = story_cards.row_header(boxes, titles)
        return None if box is None else box.y + box.height / 2

    def _reference_frame(self):
        return cv2.resize(self.capture_frame()[:, :, :3], (REFERENCE_WIDTH, REFERENCE_HEIGHT))

    def _drag_row(self, header_y: float, from_x: int, to_x: int) -> None:
        frame = self.capture_frame()
        height, width = frame.shape[:2]
        y = round((header_y + ROW_DRAG_BELOW_HEADER) / REFERENCE_HEIGHT * height)
        self.drag_client(
            (round(from_x / REFERENCE_WIDTH * width), y),
            (round(to_x / REFERENCE_WIDTH * width), y),
            duration=ROW_DRAG_SECONDS,
            after_sleep=1.0,
        )

    def _first_unfinished_in_row(self, row_name: str, header_y: float):
        """Scroll the row to its first card, then page right until a card's
        bar is not full or the row stops moving."""
        previous = None
        for _drag in range(ROW_DRAGS_MAX):
            plus = story_cards.plus_buttons(self._reference_frame(), header_y)
            if plus == previous:
                break
            previous = plus
            self._drag_row(header_y, ROW_DRAG_LEFT_X, ROW_DRAG_RIGHT_X)
        previous = None
        for _page in range(ROW_DRAGS_MAX):
            cards = story_cards.row_cards(self._reference_frame(), header_y)
            self.info_set(f"{row_name}进度", " ".join(card.bar for card in cards))
            self.log_info(
                f"{LABEL}：「{row_name}」行标题 y={header_y:.0f}，这一页 "
                + (" ".join(f"{card.plus[0]}:{card.bar}" for card in cards) or "没有卡")
            )
            card = story_cards.first_unfinished(cards)
            if card is not None:
                return card
            plus = [card.plus for card in cards]
            if not plus or plus == previous:
                return None
            previous = plus
            self._drag_row(header_y, ROW_DRAG_RIGHT_X, ROW_DRAG_LEFT_X)
        return None

    def _back_home_from_collection(self) -> bool:
        return self.home_by_key(
            lambda seconds: self._wait_for_home_confirmation(f"{LABEL}返回主页", timeout=seconds),
            f"{LABEL}返回主页",
        )

    # -- the push ------------------------------------------------------------------

    def _push(self, deadline: float) -> str:
        """Play the entered cartridge on; "cleared" or why it stopped."""
        no_progress = 60 * max(1, int(self.config.get(NO_PROGRESS_KEY, NO_PROGRESS_MINUTES)))
        last_kind, last_goal = None, ""
        progressed_at = monotonic()
        recent_kinds: deque[StoryScreen] = deque(maxlen=RECENT_SCREENS)
        quest_presses = key_presses = toggle_presses = skip_presses = defeats = 0
        preset_pending = False
        interact_detours = 0
        walking_since = None
        field_only_since = None
        while True:
            now = monotonic()
            if now >= deadline:
                return f"到了最长运行时间（{self.config.get(MAX_MINUTES_KEY, MAX_MINUTES)} 分钟）"
            if now - progressed_at >= no_progress:
                return (
                    f"{no_progress // 60} 分钟没有推进，停在「{last_kind.value if last_kind else '未知'}」"
                    f"{f'，主线目标「{last_goal}」' if last_goal else ''}（可能是解谜关或需要手动操作）"
                )
            boxes, seen = self._read_screen()
            screen, point = story_push.classify(boxes, seen)
            goal = story_push.quest_goal_text(boxes)
            new_goal = bool(goal) and not story_push.same_goal(goal, last_goal)
            if screen != last_kind or new_goal:
                if new_goal:
                    recent_kinds.clear()
                # Two screens in turn (a bystander's F button and its close-up,
                # card 18 live 2026-10-22) are not progress; a battle (re)started
                # is, losses being counted on their own.
                if new_goal or screen not in recent_kinds or screen == StoryScreen.BATTLE_AUTO:
                    progressed_at = now
                if screen != last_kind:
                    recent_kinds.append(screen)
                    self.log_info(f"{LABEL}：画面 {screen.value}")
                if new_goal:
                    self.log_info(f"{LABEL}：主线目标「{goal}」。")
                    quest_presses = key_presses = interact_detours = 0
                if screen != StoryScreen.BATTLE_READY:
                    toggle_presses = 0
                if screen != StoryScreen.TALK:
                    skip_presses = 0
            cutscene_again = screen == StoryScreen.CUTSCENE and last_kind == StoryScreen.CUTSCENE
            # One loss until another screen showed: 「重新挑战」 does nothing while
            # the defeat screen still animates in (live 2026-10-22), so it is
            # pressed again.
            defeat_again = screen == StoryScreen.BATTLE_DEFEAT and last_kind == StoryScreen.BATTLE_DEFEAT
            last_kind = screen
            if goal:
                last_goal = goal
            self.info_set("当前阶段", f"{LABEL}：{screen.value}")
            if screen != StoryScreen.UNKNOWN:
                field_only_since = None
            if screen != StoryScreen.WALKING:
                walking_since = None

            if screen == StoryScreen.HOME:
                return "home"
            if screen == StoryScreen.GUIDE:
                return "cleared"
            elif screen == StoryScreen.CLEARED:
                self.log_info(f"{LABEL}：普通难度推完了。")
                self._click_reference(*point, after_sleep=2.0)  # 不用确认：关掉完成画面后由回主页流程接手
                return "cleared"
            elif screen == StoryScreen.QUEST:
                if quest_presses < QUEST_PRESSES_BEFORE_KEY:
                    quest_presses += 1
                    self._click_reference(*point, after_sleep=1.5)  # 不用确认：推图循环下一轮重看画面
                elif key_presses < QUEST_KEY_PRESSES:
                    key_presses += 1
                    self.tap_key(story_push.QUEST_KEY, after_sleep=1.5)
                elif key_presses < QUEST_KEY_PRESSES + INTERACT_KEY_PRESSES:
                    # Already beside the goal (nowhere to walk), its button
                    # not the one matched: the interaction key.
                    key_presses += 1
                    self.tap_key(story_push.INTERACT_KEY, after_sleep=1.5)
                else:
                    return f"按了主线任务也没有开始自动移动（主线目标「{goal or last_goal}」，可能需要手动解谜）"
            elif screen == StoryScreen.WALKING:
                quest_presses = key_presses = interact_detours = 0
                walking_since = walking_since or now
                goal_point = story_push.quest_point(boxes)
                if now - walking_since >= WALK_REPATH_SECONDS and goal_point is not None:
                    walking_since = None
                    self.log_info(f"{LABEL}：自动移动太久，停下重新点主线目标。")
                    self._click_reference(*story_push.WALK_CANCEL_POINT, after_sleep=1.5)  # 不用确认：接着重点主线目标
                    self._click_reference(*goal_point, after_sleep=1.5)  # 不用确认：推图循环下一轮看是否又在移动
                else:
                    self.sleep(POLL_SECONDS)
            elif screen == StoryScreen.BATTLE_READY and preset_pending:
                preset_pending = False
                self._apply_preset(boxes, int(self.config.get(PRESET_KEY, 1) or 0))
            elif screen == StoryScreen.BATTLE_READY:
                toggle_presses += 1
                if toggle_presses <= AUTO_TOGGLE_PRESSES:
                    self._click_reference(*point, after_sleep=1.5)  # 不用确认：推图循环下一轮看「自动战斗中」
                else:
                    self.log_info(f"{LABEL}：自动战斗开关没打开，改按「BATTLE」。")
                    self._click_reference(*story_push.BATTLE_BUTTON_POINT, after_sleep=2.0)  # 不用确认：推图循环下一轮重看画面
            elif screen == StoryScreen.TALK:
                skip_presses += 1
                if skip_presses <= TALK_SKIP_PRESSES:
                    self._click_reference(*point, after_sleep=1.2)  # 不用确认：推图循环下一轮看「跳过对话」
                else:
                    self._click_reference(*story_push.TALK_ADVANCE_POINT, after_sleep=1.2)  # 不用确认：跳过无效的对话点台词往下走
            elif screen == StoryScreen.INTERACT:
                # The button shows beside anyone near; with the quest row up the
                # goal is pressed once first: walking off means this person was
                # not the goal (live 2026-10-22, card 15).
                goal_point = story_push.quest_point(boxes)
                if goal_point is not None and interact_detours < INTERACT_QUEST_FIRST:
                    interact_detours += 1
                    self._click_reference(*goal_point, after_sleep=2.0)  # 不用确认：下一轮看是走开还是停在这里
                else:
                    self._click_reference(*point, after_sleep=1.2)  # 不用确认：推图循环下一轮重看画面
            elif screen == StoryScreen.BATTLE_AUTO:
                self.sleep(POLL_SECONDS * 2)
            elif screen == StoryScreen.BATTLE_DEFEAT and defeat_again:
                self._click_reference(*point, after_sleep=3.0)  # 不用确认：下一轮重看确认框出没出来
            elif screen == StoryScreen.BATTLE_DEFEAT:
                defeats += 1
                self.log_warning(f"{LABEL}：战斗失败（第 {defeats} 次）。")
                if defeats >= DEFEATS_MAX:
                    self._leave_defeat(boxes)
                    return f"编队打输了 {defeats} 次，请先加强编队或换一个阵形预设"
                preset_pending = int(self.config.get(PRESET_KEY, 1) or 0) > 0
                self.log_info(f"{LABEL}：重新挑战。")
                self.sleep(DEFEAT_SETTLE_SECONDS)
                self._click_reference(*point, after_sleep=3.0)  # 不用确认：推图循环下一轮重看画面
            elif screen == StoryScreen.BATTLE_RESULT:
                if any(word in self._boxes_text(boxes).lower() for word in DEFEAT_WORDS):
                    defeats += 1
                    self.log_warning(f"{LABEL}：战斗失败（第 {defeats} 次）。")
                    if defeats >= DEFEATS_MAX:
                        self._click_reference(*point, after_sleep=2.0)  # 不用确认：停止前离开结算
                        return f"编队打输了 {defeats} 次，请先加强编队或换一个阵形预设"
                self._click_reference(*point, after_sleep=2.0)  # 不用确认：推图循环下一轮重看画面
            elif screen == StoryScreen.RETRY_CONFIRM:
                self.log_info(f"{LABEL}：重新挑战，从最初开始。")
                self._click_reference(*point, after_sleep=3.0)  # 不用确认：推图循环下一轮重看画面
            elif screen in (
                StoryScreen.PRESET_CONFIRM,
                StoryScreen.PRESET_PANEL,
                StoryScreen.INSERT,
                StoryScreen.CHOICE,
                StoryScreen.SKIP_CONFIRM,
                StoryScreen.DIALOG,
                StoryScreen.NPC_FOCUS,
            ) or cutscene_again:
                self._click_reference(*point, after_sleep=1.2)  # 不用确认：推图循环下一轮重看画面
            elif screen == StoryScreen.CUTSCENE:
                # A fade can read like a CG for one frame (主页 behind it):
                # clicked only on the second read in a row.
                self.sleep(POLL_SECONDS / 2)
            else:
                if self._field_hud_shown(boxes):
                    field_only_since = field_only_since or now
                    if now - field_only_since >= FIELD_ONLY_KEY_SECONDS:
                        field_only_since = None
                        self.tap_key(story_push.QUEST_KEY, after_sleep=1.5)
                        continue
                self.sleep(POLL_SECONDS)

    def _read_screen(self):
        frame = self.capture_frame()
        reference = cv2.resize(frame[:, :, :3], (REFERENCE_WIDTH, REFERENCE_HEIGHT))
        return self._reference_boxes(frame, FULL_SCREEN, LABEL), story_push.icons(reference)

    @staticmethod
    def _field_hud_shown(boxes) -> bool:
        names = {str(getattr(box, "name", "")).strip().upper() for box in boxes}
        return "SPACE" in names and "TAB" in names
