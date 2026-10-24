"""天赋升星: star up the talents the daily scripts use, once their bar is full.

Live 2026-10-24 (1080p reference): Q in a field opens the 天赋技能 panel, a
row of talent cards along the bottom.  The cards equipped in the current
skill group come first, with their slot number; a card whose experience bar
is full shows a green 「升星」 under it.  That button opens the 天赋 page,
whose 「升星 <gold>」 button (one 技能书 + gold) stars it up; the game plays
an animation, shows 「已升星。」, a tap returns to the 天赋 page and its back
arrow to the panel.

The user (2026-10-24): 「升星可以自动升级。但是只升我们在日常/脚本里面用得到
的天赋」.  Only cards named after a talent the scripts press are starred up.
A card's bar only fills by using that card, so a full bar on one of these
names is a card the scripts used.
"""

from __future__ import annotations

from qfluentwidgets import FluentIcon

from src.tasks.BaseBD2Task import BaseBD2Task, HOME_KEY, RECENT_CARTRIDGE_KEY
from src.tasks.claim_page import ClaimPageMixin, claim_button_dimmed
from src.utils.chinese import to_simplified
from src.utils.press_confirm import wait_for

LABEL = "天赋升星"
# 跑图 (探查/吸收/召集/制伏, which the game also calls 压制), 跑商 (料理, 砍价).
SCRIPT_TALENTS = ("探查", "吸收", "召集", "制伏", "压制", "料理", "砍价")

PANEL_KEY = "Q"
PANEL_TITLE_ROI = (90, 670, 200, 60)
PANEL_TITLE = "天赋技能"
# Card names (y≈927) and the 升星 buttons under them (y≈1000).
CARD_ROW_ROI = (120, 900, 1680, 140)
STAR_UP_TEXT = "升星"
# A button belongs to the name above it within this many px either way.
NAME_TO_BUTTON_X = 60
NAME_ABOVE_BUTTON = (40, 110)

# The 天赋 page.
TALENT_PAGE_TITLE_ROI = (230, 20, 330, 70)
TALENT_PAGE_TITLE = "天赋"
TALENT_STAR_UP_ROI = (1340, 955, 450, 80)
STARRED_ROI = (700, 1005, 520, 70)
STARRED_TEXT = "已升星"
STARRED_TAP_POINT = (960, 1036)
STARRED_SETTLE_SECONDS = 1.5
TALENT_PAGE_BACK_POINT = (172, 51)

FIELD_ENTRY_ATTEMPTS = 8
FIELD_ENTRY_INTERVAL = 3.0
PAGE_WAIT_SECONDS = 8.0
# The star-up animation runs about 5 s.
STARRED_WAIT_SECONDS = 15.0
MAX_STAR_UPS = 12


def script_talent(name: str) -> str:
    """The script talent a card caption names, or ''."""
    text = to_simplified(str(name))
    for talent in SCRIPT_TALENTS:
        if talent in text:
            return talent
    return ""


def star_up_targets(boxes: list) -> list[tuple[str, tuple[int, int]]]:
    """(talent, 升星 button centre) for each script talent with a lit 升星.

    ``boxes`` are the card row's OCR boxes in reference coordinates.  Left to
    right, which puts the equipped cards first.
    """
    names = []
    buttons = []
    for box in boxes:
        text = to_simplified(str(getattr(box, "name", ""))).strip()
        center = (box.x + box.width / 2, box.y + box.height / 2)
        if text == STAR_UP_TEXT:
            buttons.append(center)
        elif script_talent(text) and len(text) <= 4:
            names.append((script_talent(text), center))
    low, high = NAME_ABOVE_BUTTON
    targets = []
    for bx, by in sorted(buttons):
        for talent, (nx, ny) in names:
            if abs(nx - bx) <= NAME_TO_BUTTON_X and low <= by - ny <= high:
                targets.append((talent, (round(bx), round(by))))
                break
    return targets


class TalentStarUpTask(ClaimPageMixin, BaseBD2Task):
    recover_home_on_failure = True
    start_from_home = True
    vision_threshold_key = "加载页面阈值"
    ocr_threshold_key = "日常 OCR 阈值"
    claim_log_name = "talent_star_up"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "天赋升星"
        self.description = (
            "进最近的卡带，按 Q 打开天赋技能，日常脚本用到的天赋（探查/吸收/召集/制伏/料理/砍价）"
            "经验满了就升星（每次花 1 本技能书和金币），其他天赋不动。"
        )
        self.group_name = "日常/周常"
        self.group_icon = FluentIcon.CALENDAR
        self.icon = FluentIcon.UP
        self.visible = True
        self._init_vision_state()
        self.default_config.update(self._claim_default_config())
        self.config_description.update(self._claim_config_description())

    def run(self):
        if not bool(self.config.get("启用", True)):
            self.info_set("状态", f"{self.name}已禁用。")
            return True
        self.info_set("状态", f"启动{self.name}。")
        if not self._open_panel():
            return self._claim_fail("打开天赋技能")
        starred: list[str] = []
        for _round in range(MAX_STAR_UPS):
            targets = star_up_targets(self._card_boxes())
            self.info_set("可升星天赋", "、".join(t for t, _p in targets) or "-")
            if not targets:
                break
            talent, point = targets[0]
            result = self._star_up(talent, point)
            if result is None:
                return self._claim_fail(f"{talent}升星")
            if not result:
                break
            starred.append(talent)
        self.info_set("升星", "、".join(starred) or "-")
        if starred:
            self.log_info(f"{LABEL}：升星了 {'、'.join(starred)}。")
        else:
            self.log_info(f"{LABEL}：脚本用到的天赋都还没满，不用升星。")
        if not self._close_panel_to_home():
            return self._claim_fail("回主页")
        self.info_set("状态", f"{self.name}完成。")
        self.log_completion(f"{self.name}：流程完成。")
        return True

    # -- panel ------------------------------------------------------------

    def _panel_open(self) -> bool:
        boxes = self._reference_boxes(self.capture_frame(), PANEL_TITLE_ROI, "天赋技能标题")
        return PANEL_TITLE in to_simplified(self._boxes_text(boxes))

    def _open_panel(self) -> bool:
        """F into the recent cartridge, then Q until the panel shows (Q does
        nothing while the cartridge loads)."""
        if self._wait_for_home_confirmation(f"{LABEL}入口前主页确认", timeout=3.0):
            self.log_info(f"{LABEL}：按 {RECENT_CARTRIDGE_KEY} 进最近的卡带。")
            if not self.tap_key(RECENT_CARTRIDGE_KEY, after_sleep=FIELD_ENTRY_INTERVAL):
                return False
        for _attempt in range(FIELD_ENTRY_ATTEMPTS):
            if self._wait_for_home_confirmation(f"{LABEL}进卡带", timeout=1.0):
                # Q on 主页 is not the panel; the F was lost.
                self.tap_key(RECENT_CARTRIDGE_KEY, after_sleep=FIELD_ENTRY_INTERVAL)
                continue
            if not self.tap_key(PANEL_KEY, after_sleep=1.5):
                return False
            if wait_for(self._panel_open, 2.0, sleep=self.sleep):
                return True
            self.sleep(FIELD_ENTRY_INTERVAL)
        self._note_why("进卡带后按 Q 没打开天赋技能")
        return False

    def _card_boxes(self) -> list:
        return self._reference_boxes(self.capture_frame(), CARD_ROW_ROI, "天赋卡片")

    def _close_panel_to_home(self) -> bool:
        if self._panel_open():
            self.tap_escape(after_sleep=1.0)
        return self.home_by_key(
            lambda timeout: self._wait_for_home_confirmation(f"{LABEL}回主页", timeout=timeout),
            LABEL,
        )

    # -- one star-up ------------------------------------------------------

    def _talent_page_open(self) -> bool:
        boxes = self._reference_boxes(self.capture_frame(), TALENT_PAGE_TITLE_ROI, "天赋页标题")
        text = to_simplified(self._boxes_text(boxes))
        return TALENT_PAGE_TITLE in text and PANEL_TITLE not in text

    def _star_up(self, talent: str, point: tuple[int, int]) -> bool | None:
        """True once starred up, False when it cannot be (the panel is back),
        None when stuck off the panel."""
        opened = self.press_and_confirm(
            f"{talent}升星",
            lambda: self._click_reference(*point, after_sleep=0.5),
            self._talent_page_open,
            still_before=self._panel_open,
            timeout=PAGE_WAIT_SECONDS,
        )
        if not opened:
            self.log_info(f"{LABEL}：点「{talent}」的升星没打开天赋页。")
            return False if self._panel_open() else None
        frame = self.capture_frame()
        button = self._box_with(
            self._reference_boxes(frame, TALENT_STAR_UP_ROI, "升星按钮"), (STAR_UP_TEXT,)
        )
        if button is None or claim_button_dimmed(self._reference_frame(frame), button):
            # Short of 技能书 or gold: the button stays grey.
            self.log_info(f"{LABEL}：「{talent}」的升星按钮是灰的（技能书或金币不够），不升。")
            return self._back_to_panel(talent) and False
        self.log_info(f"{LABEL}：「{talent}」升星（按钮：{getattr(button, 'name', '')}）。")
        # retries=0: it spends a 技能书 and gold, so never pressed twice.
        starred = self.press_and_confirm(
            f"{talent}升星确认",
            lambda: self._click_reference_box(button, after_sleep=0.5),
            self._starred_shown,
            timeout=STARRED_WAIT_SECONDS,
            retries=0,
        )
        if not starred:
            self.log_info(f"{LABEL}：「{talent}」按了升星没看到「已升星」。")
            return self._back_to_panel(talent) and False
        # Live 2026-10-24: 「已升星。」 reads before the animation takes taps; a
        # tap then was lost, and the back press after it only dismissed it.
        self.sleep(STARRED_SETTLE_SECONDS)
        self.press_and_confirm(
            f"{talent}已升星",
            lambda: self._click_reference(*STARRED_TAP_POINT, after_sleep=0.5),
            self._talent_page_open,
            still_before=self._starred_shown,
            timeout=PAGE_WAIT_SECONDS,
            retries=2,
        )
        return self._back_to_panel(talent)

    def _starred_shown(self) -> bool:
        boxes = self._reference_boxes(self.capture_frame(), STARRED_ROI, "已升星")
        return STARRED_TEXT in to_simplified(self._boxes_text(boxes))

    def _back_to_panel(self, talent: str) -> bool:
        if self._panel_open():
            # Back on the panel already: its top-left arrow leaves the field.
            return True
        back = self.press_and_confirm(
            f"{talent}天赋页返回",
            lambda: self._click_reference(*TALENT_PAGE_BACK_POINT, after_sleep=0.5),
            self._panel_open,
            still_before=self._talent_page_open,
            timeout=PAGE_WAIT_SECONDS,
        )
        if not back:
            self._note_why(f"「{talent}」的天赋页按返回没回到天赋技能")
        return bool(back)

    @staticmethod
    def _reference_frame(frame):
        import cv2

        from src.tasks.task_vision_mixin import REFERENCE_HEIGHT, REFERENCE_WIDTH

        if frame.shape[1] == REFERENCE_WIDTH and frame.shape[0] == REFERENCE_HEIGHT:
            return frame
        return cv2.resize(frame, (REFERENCE_WIDTH, REFERENCE_HEIGHT), interpolation=cv2.INTER_AREA)
