"""Reading the 格鲁TALK (GLU TALK) window (1920x1080 reference, calibrated
on the bd2 session's 简体 1080p client 2026-11-06, tests/fixtures/glu_talk).

主页 → 格鲁TALK opens a window over 主页.  Its header reads
「今日的剩余相遇 | 3」: three free encounters a day (09:00 KST, the daily
reset); the ⊕ beside it buys three more with 钻石 or 装饰币 and is never
pressed.  The left strip has two tabs: 缘分列表 (people) and 未读消息
(chats).  Each row of the chat list shows a pink heart with the person's
level (1-10) and their name; 缘分候选 (no heart yet) are not in it.

A chat is played on the right: the person's lines come one by one, then
「发送消息」 with the reply under it (one so far, pressed).  At the end a
card 「相遇事件 EP.07 第7次相遇 [进行相遇事件]」; pressed, a dialog
「是否要进行相遇事件？可进行次数：3次 [取消] [确认]」, then a story scene
(F2 跳过 → 「跳过对话」 [取消] [确认]), then 「获得好感度奖励」 (the level
up, 50 钻石) and 「获得好感度特效！」 (a picture with a back arrow and
「主界面设置」, which is never pressed) and the window again, the card
now 「完成相遇事件」.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np

from src.utils.ocr_utils import normalize_ocr_text

LEVEL_MAX = 10
ENCOUNTERS_PER_DAY = 3

# -- home ---------------------------------------------------------------------
ENTRY_POINT = (264, 258)  # 主页 left column, the 格鲁TALK icon
HOME_ENTRY_ROI = (60, 80, 520, 320)
HOME_ENTRY_WORDS = ("格鲁TALK", "格鲁talk")
HOME_ICON_ABOVE_LABEL = 42  # label at y 300, its icon at 258

# -- window -------------------------------------------------------------------
HEADER_ROI = (480, 245, 960, 55)  # GLU TALK … 今日的剩余相遇 | 3 (stops before ⊕)
WINDOW_WORDS = ("今日的剩余相遇", "GLU TALK", "GLUTALK")
REMAINING_WORD = "剩余相遇"
CLOSE_POINT = (1497, 273)
CHATS_TAB_POINT = (440, 452)
LIST_HEADER_ROI = (495, 310, 520, 60)  # 「未读消息 10」 on the chat tab
CHATS_TAB_WORDS = ("未读消息", "消息")
# The rows: heart column and the name right of it.
LIST_ROI = (495, 375, 510, 495)
HEART_COLUMN = (585, 640)
# Stops before the unread badge (「1」 at x 976), which goes once the chat is read.
ROW_NAME_X = (625, 940)
ROW_NAME_HALF_HEIGHT = 16
ROW_PRESS_X = 760
LIST_SCROLL_POINT = (750 / 1920, 650 / 1080)

# -- chat ---------------------------------------------------------------------
CHAT_ROI = (1010, 300, 530, 570)
SEND_WORD = "发送消息"
START_WORD = "进行相遇事件"
DONE_WORD = "完成相遇事件"

# -- encounter ----------------------------------------------------------------
DIALOG_ROI = (660, 330, 600, 420)
DIALOG_WORDS = ("是否要进行相遇事件",)
DIALOG_COUNT_WORD = "可进行次数"
# A dialog that would spend 钻石 or 装饰币 is never confirmed.
PAID_WORDS = ("钻石", "装饰币", "购买")
SKIP_POINT = (1638, 60)  # F2
SKIP_DIALOG_ROI = (660, 250, 600, 600)
SKIP_DIALOG_WORDS = ("跳过对话",)
REWARD_WORDS = ("获得好感度奖励",)
EFFECT_WORDS = ("获得好感度特效", "主界面设置")
REWARD_TAP_POINT = (960, 900)
EFFECT_BACK_POINT = (172, 50)
SCENE_ADVANCE_POINT = (960, 1000)


@dataclass(frozen=True)
class Row:
    name: str
    level: int | None
    y: int  # reference y of the heart / the name line

    @property
    def key(self) -> str:
        return name_key(self.name)


def name_key(name: str) -> str:
    return normalize_ocr_text(name)


def read_remaining(text: str) -> int | None:
    """「今日的剩余相遇 | 3」 → 3; None when the count was not read."""
    flat = normalize_ocr_text(text)
    at = flat.find(normalize_ocr_text(REMAINING_WORD))
    if at < 0:
        return None
    match = re.search(r"(\d+)", flat[at:])
    if match is None:
        return None
    value = int(match.group(1))
    return value if value <= 2 * ENCOUNTERS_PER_DAY else None


def read_dialog_count(text: str) -> int | None:
    """「可进行次数：2次」 → 2."""
    flat = normalize_ocr_text(text)
    match = re.search(r"可进行次数[:：]?(\d+)", flat)
    return int(match.group(1)) if match else None


def dialog_is_free(text: str) -> bool:
    """The encounter dialog with a count left and nothing paid on it."""
    count = read_dialog_count(text)
    if count is None or count < 1:
        return False
    flat = normalize_ocr_text(text)
    return not any(word in flat for word in PAID_WORDS)


def to_reference(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    image = frame[:, :, :3]
    if (width, height) == (1920, 1080):
        return image
    return cv2.resize(image, (1920, 1080), interpolation=cv2.INTER_AREA)


def find_hearts(reference: np.ndarray) -> list[tuple[int, int, int, int]]:
    """The pink level hearts in the list column: (x, y, w, h), top to bottom."""
    x0, x1 = HEART_COLUMN
    _lx, ly, _lw, lh = LIST_ROI
    roi = reference[ly : ly + lh, x0:x1].astype(np.int16)
    blue, green, red = roi[:, :, 0], roi[:, :, 1], roi[:, :, 2]
    mask = (red > 180) & (green < 120) & (blue > 70) & (blue < 200) & (red - green > 100)
    count, _labels, stats, _centres = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    hearts = []
    for index in range(1, count):
        x, y, w, h, area = stats[index]
        # 28x25 at 1080p; a partly scrolled-off heart is left for the next look.
        if area < 150 or not 20 <= w <= 36 or not 18 <= h <= 32:
            continue
        hearts.append((int(x0 + x), int(ly + y), int(w), int(h)))
    return sorted(hearts, key=lambda heart: heart[1])


def heart_digit_image(reference: np.ndarray, heart: tuple[int, int, int, int]) -> np.ndarray:
    """The white digit inside a heart as black on white, enlarged for OCR.

    The digit read straight off the pink heart came back empty for 「1」 and
    now and then for the others (live 2026-11-06); thresholded it read every
    level on four list frames.
    """
    x, y, w, h = heart
    crop = reference[y : y + h, x : x + w]
    ink = np.where(crop.min(axis=2) > 170, 0, 255).astype(np.uint8)
    big = cv2.resize(ink, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
    big = cv2.copyMakeBorder(big, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
    return cv2.cvtColor(big, cv2.COLOR_GRAY2BGR)


def read_level(text: str) -> int | None:
    digits = re.sub(r"\D", "", str(text))
    if not digits:
        return None
    value = int(digits)
    return value if 1 <= value <= LEVEL_MAX else None


def row_name(boxes: list, heart_y: int) -> str:
    """The name on a heart's line: boxes (reference coords) right of it."""
    words = []
    for box in boxes:
        name = str(getattr(box, "name", "") or "")
        centre_x = float(box.x) + float(box.width) / 2
        centre_y = float(box.y) + float(box.height) / 2
        if not name or not ROW_NAME_X[0] <= centre_x <= ROW_NAME_X[1]:
            continue
        if abs(centre_y - heart_y) <= ROW_NAME_HALF_HEIGHT:
            words.append((float(box.x), name))
    text = " ".join(name for _x, name in sorted(words)).strip()
    # A heart digit read into the name box (「6 被封印的欲望 阿奇拉」) would
    # change with the level and lose the row after its encounter.
    return re.sub(r"^\d+\s*", "", text).strip()


def choose(rows: list[Row], level_below: int = LEVEL_MAX) -> list[Row]:
    """People below ``level_below``, highest level first (list order on ties).

    User 2026-11-06: 「只选择等级小于10的…等级越高越优先选择」.
    """
    seen: set[str] = set()
    picked = []
    for row in rows:
        if row.level is None or row.level >= level_below or row.key in seen or not row.key:
            continue
        seen.add(row.key)
        picked.append(row)
    return sorted(picked, key=lambda row: -int(row.level or 0))


@dataclass(frozen=True)
class ChatStep:
    kind: str  # reply | start | done | wait
    box: object | None = None


def chat_step(boxes: list) -> ChatStep:
    """What the chat panel wants next, from its OCR boxes (any coords).

    The lowest of 发送消息 / 进行相遇事件 / 完成相遇事件 is the current one:
    older cards and replies stay above it in the scrolled history.
    """
    def centre_y(box) -> float:
        return float(box.y) + float(box.height) / 2

    def flat(box) -> str:
        return normalize_ocr_text(getattr(box, "name", "") or "")

    marks = []
    for box in boxes:
        text = flat(box)
        if START_WORD in text:
            marks.append(("start", box))
        elif DONE_WORD in text:
            marks.append(("done", box))
        elif text == SEND_WORD or (SEND_WORD in text and len(text) <= len(SEND_WORD) + 1):
            marks.append(("send", box))
    if not marks:
        return ChatStep("wait")
    kind, mark = max(marks, key=lambda item: centre_y(item[1]))
    if kind == "send":
        below = [
            box for box in boxes
            if centre_y(box) > centre_y(mark) + 10 and flat(box) and box is not mark
        ]
        if not below:
            return ChatStep("wait")
        return ChatStep("reply", min(below, key=centre_y))
    return ChatStep(kind, mark)
