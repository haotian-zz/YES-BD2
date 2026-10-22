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

from time import monotonic

import cv2
from qfluentwidgets import FluentIcon

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

LABEL = "主线推图"
CONTINUE_KEY = "持续推进"
NO_PROGRESS_KEY = "无进展停止分钟"
MAX_MINUTES_KEY = "最长运行分钟"
NO_PROGRESS_MINUTES = 5
MAX_MINUTES = 180
# Quest-row presses on one goal without the walk starting before E is tried,
# and E presses after that before the run stops.
QUEST_PRESSES_BEFORE_KEY = 3
QUEST_KEY_PRESSES = 2
# Auto-battle toggle presses on one battle before 「BATTLE」 is pressed instead.
AUTO_TOGGLE_PRESSES = 3
# Lost battles in one cartridge before the run stops.
DEFEATS_MAX = 2
DEFEAT_WORDS = ("defeat",)
# The field HUD (SPACE / TAB under the skill wheel) with the quest row unread:
# E after this long.
FIELD_ONLY_KEY_SECONDS = 4.0
POLL_SECONDS = 1.0


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
            "剧情跳过、战斗用默认编队自动战斗，一直推到这张卡打完。"
        )
        self.icon = FluentIcon.PLAY
        self.group_name = "推图"
        self.default_config[CONTINUE_KEY] = True
        self.default_config[NO_PROGRESS_KEY] = NO_PROGRESS_MINUTES
        self.default_config[MAX_MINUTES_KEY] = MAX_MINUTES
        self.config_description[CONTINUE_KEY] = "一张剧情游戏卡打完后，接着推下一张没打完的。"
        self.config_description[NO_PROGRESS_KEY] = (
            "这么多分钟画面一直没有推进（例如解谜关、默认编队打不过）就停下，并说明停在哪里。"
        )
        self.config_description[MAX_MINUTES_KEY] = "整次推图最多跑这么多分钟。"

    # -- entry --------------------------------------------------------------------

    def run_claim(self) -> bool:
        deadline = monotonic() + 60 * max(1, int(self.config.get(MAX_MINUTES_KEY, MAX_MINUTES)))
        cleared = 0
        inside = self._story_screen_now()
        while True:
            if inside:
                inside = False
                card = "当前的剧情游戏卡"
                self.log_info(f"{LABEL}：已经在剧情游戏卡里，直接推图。")
                outcome = self._push(deadline)
                if outcome != "cleared":
                    self._note_why(outcome)
                    self._save_flow_diagnostic("story_push_stopped")
                    return self._claim_fail("推图")
                cleared += 1
                self.log_info(f"{LABEL}：{card} 已推完（本次第 {cleared} 张）。")
                if not bool(self.config.get(CONTINUE_KEY, True)) or monotonic() >= deadline:
                    return self._field_to_home()
                if not self._field_to_home():
                    return self._claim_fail("返回主页")
                continue
            if not self._open_page_from_home(
                "游戏卡珍藏集", CARTRIDGE_SLOT_POINT, COLLECTION_TITLE_KEYWORDS
            ):
                return self._claim_fail("打开游戏卡珍藏集")
            card = self._enter_unfinished_story_card()
            if card is None:
                return self._claim_fail("进入剧情游戏卡")
            if card == "none":
                self.log_info(f"{LABEL}：剧情游戏卡都已推完。")
                return self._back_home_from_collection()
            outcome = self._push(deadline)
            if outcome != "cleared":
                self._note_why(outcome)
                self._save_flow_diagnostic("story_push_stopped")
                return self._claim_fail("推图")
            cleared += 1
            self.log_info(f"{LABEL}：{card} 已推完（本次第 {cleared} 张）。")
            if not bool(self.config.get(CONTINUE_KEY, True)) or monotonic() >= deadline:
                return self._field_to_home()
            if not self._field_to_home():
                return self._claim_fail("返回主页")

    def _story_screen_now(self) -> bool:
        """Two reads in a row show a story screen (talk, CG, battle, field)."""
        for look in range(2):
            if look:
                self.sleep(0.8)
            boxes = self._reference_boxes(self.capture_frame(), None, LABEL)
            screen, _point = story_push.classify(boxes)
            if screen == StoryScreen.UNKNOWN and not self._field_hud_shown(boxes):
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
        for row_name, titles in ROWS:
            header_y = self._row_header_y(titles)
            if header_y is None:
                self.log_info(f"{LABEL}：游戏卡珍藏集里没看到「{row_name}」这一排。")
                continue
            card = self._first_unfinished_in_row(row_name, header_y)
            if card is None:
                continue
            label = f"{row_name}（{'推到一半' if card.bar == story_cards.PLAYING else '没开始'}的那张）"
            self.log_info(f"{LABEL}：进入{label}。")
            self._click_reference(*card.click_point, after_sleep=2.0)  # 不用确认：推图循环接着看画面
            return label
        return "none"

    def _row_header_y(self, titles) -> float | None:
        boxes = self._reference_boxes(self.capture_frame(), None, "珍藏集行标题")
        box = self._box_with(boxes, titles)
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
        quest_presses = key_presses = toggle_presses = defeats = 0
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
            boxes = self._reference_boxes(self.capture_frame(), None, LABEL)
            screen, point = story_push.classify(boxes)
            goal = story_push.quest_goal_text(boxes)
            if screen != last_kind or (goal and goal != last_goal):
                progressed_at = now
                if screen != last_kind:
                    self.log_info(f"{LABEL}：画面 {screen.value}")
                if goal and goal != last_goal:
                    self.log_info(f"{LABEL}：主线目标「{goal}」。")
                    quest_presses = key_presses = 0
                if screen != StoryScreen.BATTLE_READY:
                    toggle_presses = 0
            last_kind = screen
            if goal:
                last_goal = goal
            self.info_set("当前阶段", f"{LABEL}：{screen.value}")
            if screen != StoryScreen.UNKNOWN:
                field_only_since = None

            if screen == StoryScreen.QUEST:
                if quest_presses < QUEST_PRESSES_BEFORE_KEY:
                    quest_presses += 1
                    self._click_reference(*point, after_sleep=1.5)  # 不用确认：推图循环下一轮重看画面
                elif key_presses < QUEST_KEY_PRESSES:
                    key_presses += 1
                    self.tap_key(story_push.QUEST_KEY, after_sleep=1.5)
                else:
                    return f"按了主线任务也没有开始自动移动（主线目标「{goal or last_goal}」，可能需要手动解谜）"
            elif screen == StoryScreen.WALKING:
                quest_presses = key_presses = 0
                self.sleep(POLL_SECONDS)
            elif screen == StoryScreen.BATTLE_READY:
                toggle_presses += 1
                if toggle_presses <= AUTO_TOGGLE_PRESSES:
                    self._click_reference(*point, after_sleep=1.5)  # 不用确认：推图循环下一轮看「自动战斗中」
                else:
                    self.log_info(f"{LABEL}：自动战斗开关没打开，改按「BATTLE」。")
                    self._click_reference(*story_push.BATTLE_BUTTON_POINT, after_sleep=2.0)  # 不用确认：推图循环下一轮重看画面
            elif screen == StoryScreen.BATTLE_AUTO:
                self.sleep(POLL_SECONDS * 2)
            elif screen == StoryScreen.BATTLE_RESULT:
                if any(word in self._boxes_text(boxes).lower() for word in DEFEAT_WORDS):
                    defeats += 1
                    self.log_warning(f"{LABEL}：战斗失败（第 {defeats} 次）。")
                    if defeats >= DEFEATS_MAX:
                        self._click_reference(*point, after_sleep=2.0)  # 不用确认：停止前离开结算
                        return f"默认编队打输了 {defeats} 次，请先加强编队"
                self._click_reference(*point, after_sleep=2.0)  # 不用确认：推图循环下一轮重看画面
            elif screen in (
                StoryScreen.INSERT,
                StoryScreen.TALK,
                StoryScreen.SKIP_CONFIRM,
                StoryScreen.INTERACT,
                StoryScreen.CUTSCENE,
            ):
                self._click_reference(*point, after_sleep=1.2)  # 不用确认：推图循环下一轮重看画面
            else:
                if self._field_hud_shown(boxes):
                    field_only_since = field_only_since or now
                    if now - field_only_since >= FIELD_ONLY_KEY_SECONDS:
                        field_only_since = None
                        self.tap_key(story_push.QUEST_KEY, after_sleep=1.5)
                        continue
                self.sleep(POLL_SECONDS)

    @staticmethod
    def _field_hud_shown(boxes) -> bool:
        names = {str(getattr(box, "name", "")).strip().upper() for box in boxes}
        return "SPACE" in names and "TAB" in names
