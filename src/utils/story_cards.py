"""Story cartridges on the 游戏卡珍藏集 page and how far each is played.

Read live on the bd2 session 2026-10-22 (1920x1080 reference, sort 「123」):

- each row has a header (「剧情游戏卡 15／20」, 「店长游戏卡 1／2」) with its
  cards under it at a 280 px pitch, scrolled sideways by dragging the row;
- an owned card has a round 「+」 button top right (header + 72..74); a card
  not owned yet (TRIPLE ALLIANCE, WAY OF THE DEMON) is shrink-wrapped and has
  none;
- the progress bar is 146 x 4 px at header + 196..206, from 149 to 3 px left
  of the 「+」: white and full when the difficulty is played through, a dark
  track with a yellow part while it is being played (卡 15: 82/146), and no
  bar at all before the card was started (DIMENSIONS; the user: 「没有进度条
  =没开始」).

The user (2026-10-22): enter the first card whose bar is not full, the
剧情游戏卡 row first, then the 店长游戏卡 row.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from src.utils.image_utils import template_match_response
from src.utils.ocr_utils import normalize_ocr_text

PLUS_TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "recognition-assets" / "template-assets" / "story_push" / "card_plus_button.png"
)
PLUS_MIN_SCORE = 0.75
PLUS_BAND = (55, 95)  # below the header centre
PLUS_SPACING = 200  # two hits closer than this are one card
BAR_BAND = (194, 210)
BAR_LEFT, BAR_RIGHT = 149, 3  # left of the 「+」 centre
BAR_FULL_WHITE = 0.85
# A card is clicked on its art, left of and under the 「+」.
CARD_CLICK_OFFSET = (-76, 50)
# Cards whose 「+」 sits this close to an edge are only partly on screen.
EDGE_MARGIN = 40

STORY_ROW_TITLES = ("剧情游戏卡", "劇情遊戲卡")
MASTER_ROW_TITLES = ("店长游戏卡", "店長遊戲卡")

FULL, PLAYING, NOT_STARTED = "full", "playing", "not_started"


@dataclass(frozen=True)
class StoryCard:
    plus: tuple[int, int]
    bar: str

    @property
    def click_point(self) -> tuple[int, int]:
        return self.plus[0] + CARD_CLICK_OFFSET[0], self.plus[1] + CARD_CLICK_OFFSET[1]

    @property
    def finished(self) -> bool:
        return self.bar == FULL


_template_cache: list[np.ndarray] = []


def _plus_template() -> np.ndarray | None:
    if not _template_cache:
        template = cv2.imread(str(PLUS_TEMPLATE), cv2.IMREAD_GRAYSCALE)
        if template is None:
            return None
        _template_cache.append(template)
    return _template_cache[0]


def plus_buttons(frame_1080: np.ndarray, header_y: float, template: np.ndarray | None = None) -> list[tuple[int, int]]:
    """Centres of the 「+」 buttons of the owned cards under a row header, left to right."""
    template = template if template is not None else _plus_template()
    if template is None:
        return []
    height, width = frame_1080.shape[:2]
    top = max(0, round(header_y + PLUS_BAND[0] - template.shape[0] / 2))
    bottom = min(height, round(header_y + PLUS_BAND[1] + template.shape[0] / 2))
    band = cv2.cvtColor(frame_1080[top:bottom, :, :3], cv2.COLOR_BGR2GRAY)
    if band.shape[0] < template.shape[0]:
        return []
    response = template_match_response(band, template).copy()
    found: list[tuple[int, int]] = []
    th, tw = template.shape[:2]
    while True:
        _low, score, _where, (x, y) = cv2.minMaxLoc(response)
        if score < PLUS_MIN_SCORE:
            break
        centre = (x + tw // 2, top + y + th // 2)
        if EDGE_MARGIN <= centre[0] <= width - EDGE_MARGIN:
            found.append(centre)
        response[:, max(0, x - PLUS_SPACING // 2) : x + PLUS_SPACING // 2] = -1
    return sorted(found)


def bar_state(frame_1080: np.ndarray, header_y: float, plus_x: int) -> str:
    left, right = plus_x - BAR_LEFT, plus_x - BAR_RIGHT
    top, bottom = round(header_y + BAR_BAND[0]), round(header_y + BAR_BAND[1])
    patch = frame_1080[max(0, top) : bottom, max(0, left) : right, :3]
    if patch.size == 0:
        return NOT_STARTED
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    white = (hsv[:, :, 2] >= 200) & (hsv[:, :, 1] <= 40)
    yellow = (hsv[:, :, 0] >= 15) & (hsv[:, :, 0] <= 35) & (hsv[:, :, 1] >= 120) & (hsv[:, :, 2] >= 170)
    if float(white.mean(axis=1).max()) >= BAR_FULL_WHITE:
        return FULL
    if float(yellow.mean(axis=1).max()) >= 0.03:
        return PLAYING
    return NOT_STARTED


def row_cards(frame_1080: np.ndarray, header_y: float, template: np.ndarray | None = None) -> list[StoryCard]:
    return [
        StoryCard(plus, bar_state(frame_1080, header_y, plus[0]))
        for plus in plus_buttons(frame_1080, header_y, template)
    ]


def first_unfinished(cards: list[StoryCard]) -> StoryCard | None:
    return next((card for card in cards if not card.finished), None)


def row_header(boxes, titles):
    """The row's header box: its text starts with the title (「剧情游戏卡 16／20」).

    The 店长 row's subtitle 「「棕色尘埃2」主线剧情游戏卡」 also holds
    「剧情游戏卡」 (live 2026-10-22), so a mere substring is not enough."""
    wanted = [normalize_ocr_text(title) for title in titles]
    for box in boxes or ():
        text = normalize_ocr_text(getattr(box, "name", ""))
        if any(text.startswith(title) for title in wanted):
            return box
    return None


# A card played through on one difficulty with the next one open carries a
# red 「Ⅱ 可进行困难难度」 (or 极难) banner under its art; that difficulty's
# first clear pays 钻石 (card 1 困难 + 极难: 1030, live 2026-10-23).  The art
# centre is about 100 px above the banner, at the same x.
DIFFICULTY_BANNER_TEXTS = ("可进行困难难度", "可进行极难难度", "可進行困難難度", "可進行極難難度")
DIFFICULTY_BANNER_TO_CARD = -100
# Same card on a re-read page: its point moves by a few pixels only.
SKIP_NEAR = 80
# Read on the whole page the light banner text is often missed (live
# 2026-10-23: card 13's 「可进行极难难度」 under a read 「剧情游戏卡」 title);
# a strip at the banners' height under each row title reads it.
BANNER_ROW_TITLES = STORY_ROW_TITLES + ("角色游戏卡", "角色遊戲卡")
BANNER_BELOW_TITLE = 227
BANNER_STRIP_HEIGHT = 80
# 「查看战场奖励」 top right swaps the banners for reward icons.  Its switch
# is gold on the left while on (BGR ~(62,142,182)) and a white knob there
# while off (~(210,218,222)), live 2026-10-23.
REWARDS_SWITCH_LEFT = (1685, 44, 1715, 58)
REWARDS_SWITCH_POINT = (1715, 50)
REWARDS_SWITCH_GOLD = 70  # red minus blue


def difficulty_card(boxes, skip=()):
    """(banner text, card click point) of the top-left card with a difficulty
    banner, or None; cards whose point lies near one in ``skip`` (lost there
    before) are passed over."""
    wanted = [normalize_ocr_text(text) for text in DIFFICULTY_BANNER_TEXTS]
    banners = []
    for box in boxes or ():
        text = normalize_ocr_text(getattr(box, "name", ""))
        if any(word in text for word in wanted):
            banners.append(box)
    for box in sorted(banners, key=lambda b: (round(b.y / 100), b.x)):
        x = round(box.x + box.width / 2)
        y = round(box.y + box.height / 2 + DIFFICULTY_BANNER_TO_CARD)
        if not any(abs(x - sx) < SKIP_NEAR and abs(y - sy) < SKIP_NEAR for sx, sy in skip):
            return str(box.name), (x, y)
    return None


def banner_strips(boxes):
    """(x, y, w, h) strips at the banner height under each story/character
    row title on the page."""
    titles = [normalize_ocr_text(title) for title in BANNER_ROW_TITLES]
    strips = []
    for box in boxes or ():
        if not any(normalize_ocr_text(getattr(box, "name", "")).startswith(title) for title in titles):
            continue
        top = round(box.y + box.height / 2 + BANNER_BELOW_TITLE - BANNER_STRIP_HEIGHT / 2)
        if 0 <= top and top + BANNER_STRIP_HEIGHT <= 1080:
            strips.append((0, top, 1920, BANNER_STRIP_HEIGHT))
    return strips


def rewards_switch_on(frame_1080: np.ndarray) -> bool:
    left, top, right, bottom = REWARDS_SWITCH_LEFT
    b, _g, r = frame_1080[top:bottom, left:right, :3].reshape(-1, 3).mean(0)
    return float(r) - float(b) > REWARDS_SWITCH_GOLD
