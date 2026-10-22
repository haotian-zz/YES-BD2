"""主线推图: what the screen asks for while a story cartridge plays itself.

Flow from the user (2026-10-22): in a story cartridge, press the top-right
main-quest row (主线, or its E key) and the party walks by itself
(「自动移动中：主线任务」) to the next point; talks are skipped, battles run
with the default formation on the game's own auto battle, and the quest row
is pressed again.  Screens met live on the bd2 session the same day
(剧情卡 15 PROMISE OF VENGEANCE, 普通):

- talk: speech bubbles with F1 记录 / F2 跳过 / F3 自动 top right; 跳过 opens
  「跳过对话 / 是否结束剧情观看？」 with 取消 / 确认;
- full-screen CG: no buttons, at most a subtitle (speaker + line) bottom
  centre over a ⬇ mark; a click anywhere goes on;
- arrival at a person: 「F 对话」 over them and an extra round button with an
  「F」 label left of the skill wheel;
- battle: 「TURN.1」 top, 「TURN.1 BATTLE」 bottom right, the auto-battle
  toggle (▶ in a ring) top right; once on: 「自动战斗中」 bottom left and
  「结束自动战斗 ESC」 bottom right; the result ends on 「离开」 bottom right.

Every box here is in 1920x1080 reference coordinates (name, x, y, width,
height), as ``ClaimPageMixin._reference_boxes`` gives them.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path

import cv2
import numpy as np

from src.utils.field_battle import AUTO_TEXTS, LEAVE_TEXTS, TURN_PATTERN
from src.utils.ocr_utils import normalize_ocr_text


class StoryScreen(str, Enum):
    CLEARED = "cleared"
    GUIDE = "guide"
    INSERT = "insert"
    SKIP_CONFIRM = "skip_confirm"
    DIALOG = "dialog"
    CHOICE = "choice"
    TALK = "talk"
    BATTLE_AUTO = "battle_auto"
    BATTLE_RESULT = "battle_result"
    BATTLE_READY = "battle_ready"
    NPC_FOCUS = "npc_focus"
    INTERACT = "interact"
    WALKING = "walking"
    QUEST = "quest"
    CUTSCENE = "cutscene"
    UNKNOWN = "unknown"


# The cartridge's difficulty played through: 「完成主线任务普通 / 已完成普通难度的
# 所有探索。」 over a character art and the rewards, until a click (card 1,
# live 2026-10-22).
CLEARED_TEXTS = ("完成主线任务", "已完成普通难度", "已完成普通難度")
CLEARED_POINT = (960, 900)
# Then (WAY OF THE DEMON, same day) the cartridge's 「指南」 book: 普通 完成 /
# 困难 可进行, and 「前往游戏卡珍藏集」 bottom right; Esc and H do nothing there.
# That button goes back to 主页, which shows one 「主线任务解锁」 card per
# difficulty just opened (困难 of the cards played) until ✕ top right.
GUIDE_TEXTS = ("前往游戏卡珍藏集", "前往遊戲卡珍藏集")
UNLOCK_TEXTS = ("主线任务解锁", "主線任務解鎖")
UNLOCK_CLOSE_POINT = (1770, 52)
# A cartridge entered for the first time: 「未插好游戏卡。请通过多次点击开始游戏。」
# under the card, a ring to click (Enter or Space) over it (SOUL-WAGER, 2026-10-22).
INSERT_TEXTS = ("未插好游戏卡", "未插好遊戲卡")
INSERT_POINT = (960, 654)
SKIP_TITLES = ("跳过对话", "跳過對話")
CONFIRM_TEXTS = ("确认", "確認")
SKIP_CONFIRM_ROI = (900, 700, 1200, 850)
# A field dialog opened by a stray click (the 「战场角色设置」 icon sits bottom
# centre of the field, live 2026-10-22): 取消 closes it.
DIALOG_TITLES = ("战场角色设置", "戰場角色設置")
CANCEL_TEXTS = ("取消",)
# F2 label under the talk's 跳过 icon; the icon itself is pressed.
TALK_SKIP_LABEL = "F2"
TALK_SKIP_LABEL_ROI = (1550, 70, 1720, 130)
TALK_SKIP_POINT = (1638, 60)
# A talk inside a battle (before its first turn) ignores 跳过; a click on the
# line goes on (live 2026-10-22, card 1 「打倒堕天使」).
TALK_ADVANCE_POINT = (960, 950)
# A talk asking for an answer: the options stacked bottom centre (「1 起床。」
# 「2 重新躺下。」, the card 1 prologue); the first one is taken.
CHOICE_ROI = (600, 820, 1320, 1060)
CHOICE_MIN_GAP = 50
# 「结束自动战斗」 bottom right / 「自动战斗中」 bottom left.
RESULT_LEAVE_ROI = (1300, 900, 1920, 1080)
BATTLE_BUTTON_TEXT = "battle"
BATTLE_BUTTON_ROI = (1550, 930, 1900, 1040)
BATTLE_BUTTON_POINT = (1717, 985)
AUTO_BATTLE_TOGGLE_POINT = (1490, 55)
# The interaction button (对话 / 调查 ...) that shows left of the skill wheel
# on arrival, its 「F」 label under it.
INTERACT_LABEL = "f"
INTERACT_LABEL_ROI = (1370, 915, 1450, 965)
INTERACT_POINT = (1410, 885)
INTERACT_KEY = "F"
WALKING_TEXTS = ("自动移动中", "自動移動中")
QUEST_TEXTS = ("主线", "主線")
QUEST_ROI = (1500, 100, 1920, 260)
QUEST_KEY = "E"
# The quest row's goal sits one line under 「主线」.
QUEST_GOAL_OFFSET = (30, 25)
# Goals sharing this many characters in a row are one goal read twice.
GOAL_SAME_CHARS = 4
# A CG: next to nothing to read, or a subtitle line bottom centre.  Never
# with the field HUD's 「SPACE」 / 「TAB」 labels read.  Clicked mid-screen:
# bottom centre of the field holds the 战场角色设置 icon (967, 997).
CUTSCENE_SUBTITLE_ROI = (400, 820, 1520, 960)
CUTSCENE_SUBTITLE_MIN_CHARS = 4
CUTSCENE_MAX_WORDS = 1
CUTSCENE_POINT = (960, 700)
FIELD_HUD_LABELS = ("space", "tab")


# The game's OCR reads the small 「F1 F2 F3」 / 「F」 key labels as 「日 y 因」
# (live 2026-10-22), so the talk's 跳过 icon and the interaction button are
# matched as pictures (cut from 1080 shots: 1.0 on talks, at most 0.79
# elsewhere; the search stays in their own corner).
TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "recognition-assets" / "template-assets" / "story_push"
TALK_SKIP_TEMPLATE = TEMPLATE_DIR / "talk_skip.png"
TALK_SKIP_SEARCH = (1590, 15, 100, 90)
TALK_SKIP_MIN_SCORE = 0.7
INTERACT_TEMPLATE = TEMPLATE_DIR / "interact_button.png"
INTERACT_SEARCH = (1360, 835, 100, 100)
INTERACT_MIN_SCORE = 0.85
# The interaction button pressed beside a person not on the quest (科库托斯
# 工学家, card 15) zooms in on them: a talk button right (F1) and a back
# arrow top left, no HUD.  The back arrow leaves (live 2026-10-22; 1.0
# there, at most 0.56 on 49 other shots).
NPC_FOCUS_TEMPLATE = TEMPLATE_DIR / "npc_focus_talk.png"
NPC_FOCUS_SEARCH = (1665, 780, 120, 120)
NPC_FOCUS_MIN_SCORE = 0.85
NPC_FOCUS_BACK_POINT = (172, 50)

_templates: dict[Path, np.ndarray] = {}


def icon_score(frame_1080: np.ndarray, template_path: Path, search) -> float:
    template = _templates.get(template_path)
    if template is None:
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            return 0.0
        _templates[template_path] = template
    x, y, w, h = search
    patch = frame_1080[y : y + h, x : x + w, :3]
    if patch.shape[0] < template.shape[0] or patch.shape[1] < template.shape[1]:
        return 0.0
    grey = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    return float(cv2.matchTemplate(grey, template, cv2.TM_CCOEFF_NORMED).max())


def icons(frame_1080: np.ndarray) -> dict[str, bool]:
    return {
        "talk_skip": icon_score(frame_1080, TALK_SKIP_TEMPLATE, TALK_SKIP_SEARCH) >= TALK_SKIP_MIN_SCORE,
        "interact": icon_score(frame_1080, INTERACT_TEMPLATE, INTERACT_SEARCH) >= INTERACT_MIN_SCORE,
        "npc_focus": icon_score(frame_1080, NPC_FOCUS_TEMPLATE, NPC_FOCUS_SEARCH) >= NPC_FOCUS_MIN_SCORE,
    }


def _norm(box) -> str:
    return normalize_ocr_text(getattr(box, "name", ""))


def _centre(box) -> tuple[float, float]:
    return box.x + box.width / 2, box.y + box.height / 2


def _inside(box, roi) -> bool:
    x, y = _centre(box)
    left, top, right, bottom = roi
    return left <= x <= right and top <= y <= bottom


def _find(boxes, words, roi=None):
    wanted = [normalize_ocr_text(word) for word in words]
    for box in boxes or ():
        text = _norm(box)
        if any(word and word in text for word in wanted) and (roi is None or _inside(box, roi)):
            return box
    return None


def _exact(boxes, word: str, roi):
    for box in boxes or ():
        if _norm(box) == word and _inside(box, roi):
            return box
    return None


def quest_goal_point(box) -> tuple[int, int]:
    x, y = _centre(box)
    return round(x + QUEST_GOAL_OFFSET[0]), round(y + QUEST_GOAL_OFFSET[1])


def classify(boxes, seen: dict[str, bool] | None = None) -> tuple[StoryScreen, tuple[int, int] | None]:
    """The screen and the reference point to press for it (None: just wait).

    ``seen``: ``icons(frame)``, the pictures matched on the same frame."""
    boxes = list(boxes or ())
    seen = seen or {}
    if _find(boxes, CLEARED_TEXTS):
        return StoryScreen.CLEARED, CLEARED_POINT
    guide = _find(boxes, GUIDE_TEXTS)
    if guide is not None:
        x, y = _centre(guide)
        return StoryScreen.GUIDE, (round(x), round(y))
    if _find(boxes, INSERT_TEXTS):
        return StoryScreen.INSERT, INSERT_POINT
    if _find(boxes, SKIP_TITLES):
        confirm = _find(boxes, CONFIRM_TEXTS, SKIP_CONFIRM_ROI)
        if confirm is not None:
            x, y = _centre(confirm)
            return StoryScreen.SKIP_CONFIRM, (round(x), round(y))
    if _find(boxes, DIALOG_TITLES):
        cancel = _find(boxes, CANCEL_TEXTS)
        if cancel is not None:
            x, y = _centre(cancel)
            return StoryScreen.DIALOG, (round(x), round(y))
    if _find(boxes, AUTO_TEXTS):
        return StoryScreen.BATTLE_AUTO, None
    leave = _find(boxes, LEAVE_TEXTS, RESULT_LEAVE_ROI)
    if leave is not None:
        x, y = _centre(leave)
        return StoryScreen.BATTLE_RESULT, (round(x), round(y))
    if _find(boxes, (BATTLE_BUTTON_TEXT,), BATTLE_BUTTON_ROI) and any(
        TURN_PATTERN.search(_norm(box)) for box in boxes
    ):
        return StoryScreen.BATTLE_READY, AUTO_BATTLE_TOGGLE_POINT
    if seen.get("npc_focus"):
        return StoryScreen.NPC_FOCUS, NPC_FOCUS_BACK_POINT
    if seen.get("talk_skip") or _exact(boxes, normalize_ocr_text(TALK_SKIP_LABEL), TALK_SKIP_LABEL_ROI):
        options = sorted(
            (box for box in boxes if len(_norm(box)) >= 2 and _inside(box, CHOICE_ROI)),
            key=lambda box: box.y,
        )
        if len(options) >= 2 and _centre(options[1])[1] - _centre(options[0])[1] >= CHOICE_MIN_GAP:
            x, y = _centre(options[0])
            return StoryScreen.CHOICE, (round(x), round(y))
        return StoryScreen.TALK, TALK_SKIP_POINT
    # Walking goes past people with their interaction button showing.
    if _find(boxes, WALKING_TEXTS):
        return StoryScreen.WALKING, None
    if seen.get("interact") or _exact(boxes, INTERACT_LABEL, INTERACT_LABEL_ROI):
        return StoryScreen.INTERACT, INTERACT_POINT
    quest = _find(boxes, QUEST_TEXTS, QUEST_ROI)
    if quest is not None:
        return StoryScreen.QUEST, quest_goal_point(quest)
    words = [box for box in boxes if len(_norm(box)) >= 2]
    subtitle = any(
        len(_norm(box)) >= CUTSCENE_SUBTITLE_MIN_CHARS and _inside(box, CUTSCENE_SUBTITLE_ROI)
        for box in boxes
    )
    field = any(_norm(box) in FIELD_HUD_LABELS for box in boxes)
    if not field and (len(words) <= CUTSCENE_MAX_WORDS or subtitle):
        return StoryScreen.CUTSCENE, CUTSCENE_POINT
    return StoryScreen.UNKNOWN, None


def quest_goal_text(boxes) -> str:
    """The goal line under 「主线」 (e.g. 「前往通道另一侧」), '' when unread."""
    quest = _find(boxes, QUEST_TEXTS, QUEST_ROI)
    if quest is None:
        return ""
    _x, y = _centre(quest)
    below = [
        box
        for box in boxes or ()
        if _inside(box, QUEST_ROI) and 10 <= _centre(box)[1] - y <= 45 and len(_norm(box)) >= 2
    ]
    # The goal is one line; a fading copy of it (the walk starting) can sit
    # beside it, so the widest box is taken alone.
    return str(max(below, key=lambda box: box.width).name) if below else ""


def same_goal(first: str, second: str) -> bool:
    """Two reads of one goal: the E key label (read 「日」) or a fading copy
    of the line can stick to it, a character or two misread (「日进入门内进入门内」,
    「日兰身边逃开从兰身」 for 「从兰身边逃开」, live 2026-10-22)."""
    first, second = normalize_ocr_text(first), normalize_ocr_text(second)
    if not (first and second):
        return False
    match = SequenceMatcher(None, first, second, autojunk=False).find_longest_match(0, len(first), 0, len(second))
    return match.size >= min(GOAL_SAME_CHARS, len(first), len(second))


def unlock_notice(boxes) -> bool:
    return _find(boxes, UNLOCK_TEXTS) is not None


def quest_point(boxes) -> tuple[int, int] | None:
    """The quest row's goal line to press, None when the row is unread."""
    quest = _find(boxes, QUEST_TEXTS, QUEST_ROI)
    return None if quest is None else quest_goal_point(quest)
