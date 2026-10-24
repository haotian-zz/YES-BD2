"""Mail, mission-reward, pass-reward, achievement and clear-pack claim tasks (日常收尾).

Entry points and page layouts were calibrated on the 简体 client, 2026-09-25;
see ``claim_page`` for the shared page flow.
"""

from __future__ import annotations

from qfluentwidgets import FluentIcon

from src.tasks.BaseBD2Task import BaseBD2Task
from src.tasks.claim_page import ClaimButton, ClaimPageMixin, find_red_badges
from src.tasks.task_vision_mixin import REFERENCE_HEIGHT
from src.utils.chinese import to_simplified
from src.utils.ocr_utils import keyword_match_count

# Shared left-hand tab positions on the mail and mission pages.
FIRST_TAB_POINT = (285, 151)
SECOND_TAB_POINT = (285, 221)
BOTTOM_CLAIM_ROI = (1200, 930, 720, 150)

MAIL_ENTRY_POINT = (1606, 57)
MAIL_TITLE_KEYWORDS = ("邮箱",)
MAIL_CLAIM_BUTTON = ClaimButton(BOTTOM_CLAIM_ROI, ("全部领取",))
# Both mail tabs keep the 邮箱 title, so the switch is confirmed by the
# second tab's highlight (or the claim button) changing.
MAIL_SECOND_TAB_ROI = (155, 186, 260, 70)

MISSION_ENTRY_POINT = (681, 985)
MISSION_TITLE_KEYWORDS = ("任务",)
DAILY_MISSION_TITLE = ("每日任务",)
WEEKLY_MISSION_TITLE = ("每周任务",)
MISSION_CLAIM_BUTTON = ClaimButton(BOTTOM_CLAIM_ROI, ("全部获得", "全部领取"))

# 2026-10-23: 成就 is the home bar icon right of 任务.  Its 全部 list and the
# 成就等级 page (Lv.41 and up: 1000 钻石 a level) each have a 全部获得 at the
# bottom right, at the mission page's spot.
ACHIEVEMENT_ENTRY_POINT = (785, 985)
ACHIEVEMENT_TITLE_KEYWORDS = ("成就",)
ACHIEVEMENT_LEVEL_TAB_POINT = (175, 248)
ACHIEVEMENT_LEVEL_TITLE = ("成就等级",)
ACHIEVEMENT_CLAIM_BUTTON = ClaimButton(BOTTOM_CLAIM_ROI, ("全部获得", "全部领取"))

PASS_ENTRY_POINT = (1659, 262)
PASS_TITLE_KEYWORDS = ("通行证",)
# Left column listing every active pass card (each caption ends in 通行证);
# three show at once, a fourth sits below them or after scrolling.
PASS_LIST_EXTENDED_ROI = (315, 265, 220, 440)
PASS_LIST_SCROLL_POINT = (425 / 1920, 430 / 1080)
PASS_LIST_SCROLL_ROUNDS = 2
# A caption containing this is a purchase control, never a pass card.
PASS_PURCHASE_KEYWORDS = ("购买",)
# Leo 2026-10-19: like 活动, a pass to claim carries a red ◆「!」 at its card's
# top-right corner.  The pass list is the 活动 list's widget (same x, ~107 px
# a card); the strip is a little wider and starts higher until a 4K frame of
# a badged pass pins it.
PASS_BADGE_STRIP = (490, 225, 50, 520)
PASS_BADGE_TO_CARD_CENTER = 34
PASS_CARD_X = 425
# Around the pressed card: its highlight changes when it is selected.
PASS_CARD_HALF_SIZE = (110, 50)
# Only the right half of the panel: the purchase button sits at (729, 765).
PASS_CLAIM_BUTTON = ClaimButton((1150, 700, 450, 130), ("全部获得", "全部领取"))
PASS_MAX_CARDS = 6
# Every pass has LEVEL / MISSION tabs on the right edge (live 2026-10-24).
PASS_LEVEL_TAB_POINT = (1593, 402)
PASS_MISSION_TAB_POINT = (1593, 678)
# A pass opened this many times and still badged is left (its badge is for
# something 全部获得 does not claim).
PASS_MAX_VISITS = 2

# Live 2026-10-24: 付费商店's 通关礼包 tab lists one pack per 5 story cards per
# difficulty (and per 10 欲望之塔 floors).  Each cleared card/floor has a free
# 100 钻石 tier with a 「免费」 gift button; the paid tier next to it is never
# touched.  A tab or pack with something free carries a red ◆「!」.
SHOP_ENTRY_POINT = (1097, 1000)
SHOP_TITLE_KEYWORDS = ("礼包",)
SHOP_TAB_BADGE_STRIP = (180, 110, 60, 500)
SHOP_TAB_X = 174
SHOP_TAB_BADGE_TO_CENTER = 22
SHOP_PACK_BADGE_STRIP = (395, 110, 60, 960)
SHOP_PACK_X = 330
SHOP_PACK_BADGE_TO_CENTER = 27
# The pack caption sits under its picture.
SHOP_PACK_CAPTION_BELOW_BADGE = (40, 85)
SHOP_PACK_CAPTION_X = (230, 210)
# Right half of the pack panel (the 购买 button is at x≈655 and never inside).
SHOP_FREE_ROI = (1180, 150, 560, 640)
SHOP_FREE_TEXT = "免费"
# The caption is under the gift icon; press the icon.
SHOP_FREE_ICON_ABOVE_TEXT = 30
SHOP_PACK_SCROLL_POINT = (330 / 1920, 800 / 1080)
SHOP_PACK_SCROLL_ROUNDS = 2
SHOP_MAX_TABS = 5
SHOP_MAX_PACKS = 12
SHOP_MAX_FREE_PER_PACK = 5


class _ClaimTaskBase(ClaimPageMixin, BaseBD2Task):
    recover_home_on_failure = True
    frozen_retry = True
    start_from_home = True
    vision_threshold_key = "加载页面阈值"
    ocr_threshold_key = "日常 OCR 阈值"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_name = "日常/周常"
        self.group_icon = FluentIcon.CALENDAR
        self.visible = True
        self._init_vision_state()
        self.default_config.update(self._claim_default_config())
        self.config_description.update(self._claim_config_description())

    def run(self):
        if not bool(self.config.get("启用", True)):
            self.info_set("状态", f"{self.name}已禁用。")
            return True
        self.info_set("状态", f"启动{self.name}。")
        if not self.run_claim():
            return False
        self.info_set("状态", f"{self.name}完成。")
        self.log_completion(f"{self.name}：流程完成。")
        return True

    def run_claim(self) -> bool:
        raise NotImplementedError


class MailRewardTask(_ClaimTaskBase):
    claim_log_name = "mail"
    # The reward popups go to the 跑完的结算 page's 邮件领到的.
    report_picture_kind = "mail"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "领取邮件"
        self.description = "打开邮箱，一键领取普通邮箱（可选商品邮箱）的全部邮件。"
        self.icon = FluentIcon.MAIL
        self.default_config["领取商品邮箱"] = True
        self.config_description["领取商品邮箱"] = (
            "同时领取商品邮箱（购买的礼包等）。"
        )

    def run_claim(self) -> bool:
        if not self._open_page_from_home("邮箱", MAIL_ENTRY_POINT, MAIL_TITLE_KEYWORDS):
            return self._claim_fail("打开邮箱")
        if not self._claim_all("普通邮箱", MAIL_CLAIM_BUTTON, MAIL_TITLE_KEYWORDS):
            return self._claim_fail("领取普通邮箱")
        if bool(self.config.get("领取商品邮箱", True)):
            switched = self._click_until_changed(
                "商品邮箱",
                lambda: self._click_reference(*SECOND_TAB_POINT, after_sleep=0.2),
                (MAIL_SECOND_TAB_ROI, MAIL_CLAIM_BUTTON.roi),
                wait=1.5,
            )
            if not switched:
                self.log_info("商品邮箱：分页点击后画面一直未变化，按已在商品邮箱处理。")
            if not self._claim_all("商品邮箱", MAIL_CLAIM_BUTTON, MAIL_TITLE_KEYWORDS):
                return self._claim_fail("领取商品邮箱")
        if not self._leave_to_home("邮箱", MAIL_TITLE_KEYWORDS):
            return self._claim_fail("邮箱返回主页")
        return True


class MissionRewardTask(_ClaimTaskBase):
    claim_log_name = "mission"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "领取任务奖励"
        self.description = "打开任务页，一键领取每日任务与每周任务的全部奖励。"
        self.icon = FluentIcon.ACCEPT
        self.default_config["领取每周任务"] = True
        self.config_description["领取每周任务"] = "领完每日任务后切到每周任务页再领取一次。"

    def run_claim(self) -> bool:
        if not self._open_page_from_home("任务", MISSION_ENTRY_POINT, MISSION_TITLE_KEYWORDS):
            return self._claim_fail("打开任务页")
        if not self._switch_tab("每日任务", FIRST_TAB_POINT, DAILY_MISSION_TITLE):
            return self._claim_fail("切换每日任务")
        if not self._claim_all("每日任务", MISSION_CLAIM_BUTTON, DAILY_MISSION_TITLE):
            return self._claim_fail("领取每日任务")
        if bool(self.config.get("领取每周任务", True)):
            if not self._switch_tab("每周任务", SECOND_TAB_POINT, WEEKLY_MISSION_TITLE):
                return self._claim_fail("切换每周任务")
            if not self._claim_all("每周任务", MISSION_CLAIM_BUTTON, WEEKLY_MISSION_TITLE):
                return self._claim_fail("领取每周任务")
        if not self._leave_to_home("任务", MISSION_TITLE_KEYWORDS):
            return self._claim_fail("任务页返回主页")
        return True


class AchievementRewardTask(_ClaimTaskBase):
    """2026-10-23: 成就 gives 成就经验; the 成就等级 it fills pays 钻石.  Claim
    the achievements first, then the level rewards they unlocked."""

    claim_log_name = "achievement"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "领取成就奖励"
        self.description = "打开成就页，一键领取成就经验，再到成就等级页领取等级奖励（钻石）。"
        self.icon = FluentIcon.CERTIFICATE

    def run_claim(self) -> bool:
        if not self._open_page_from_home("成就", ACHIEVEMENT_ENTRY_POINT, ACHIEVEMENT_TITLE_KEYWORDS):
            return self._claim_fail("打开成就")
        if not self._claim_all("成就", ACHIEVEMENT_CLAIM_BUTTON, ACHIEVEMENT_TITLE_KEYWORDS):
            return self._claim_fail("领取成就")
        if not self._switch_tab("成就等级", ACHIEVEMENT_LEVEL_TAB_POINT, ACHIEVEMENT_LEVEL_TITLE):
            return self._claim_fail("切换成就等级")
        if not self._claim_all("成就等级", ACHIEVEMENT_CLAIM_BUTTON, ACHIEVEMENT_LEVEL_TITLE):
            return self._claim_fail("领取成就等级")
        if not self._leave_to_home("成就", ACHIEVEMENT_TITLE_KEYWORDS):
            return self._claim_fail("成就返回主页")
        return True


class PassRewardTask(_ClaimTaskBase):
    """Leo 2026-10-19: open only the passes with a red 「!」 on the left, press
    全部获得 once on each (one press now claims mission experience and level
    rewards together), and look at the list again after every claim.  No
    second round from the top like 活动."""

    claim_log_name = "pass"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "领取通行证"
        self.description = "依次打开左侧有红点的通行证，每张点一次全部获得（绝不点购买）。"
        self.icon = FluentIcon.TAG

    def run_claim(self) -> bool:
        if not self._open_page_from_home("通行证", PASS_ENTRY_POINT, PASS_TITLE_KEYWORDS):
            return self._claim_fail("打开通行证")
        self._pass_cards()  # the captions go to the run info
        skipped: dict[str, str] = {}
        visits: dict[str, int] = {}
        claimed = 0
        scrolls = 0
        for _step in range(PASS_MAX_CARDS * PASS_MAX_VISITS + PASS_LIST_SCROLL_ROUNDS + 1):
            frame = self.capture_frame()
            target = self._next_pass_badge(frame, skipped)
            if target is None:
                if scrolls >= PASS_LIST_SCROLL_ROUNDS:
                    break
                scrolls += 1
                self.info_set("当前阶段", "通行证：向下滚动列表查找更多红点")
                self.scroll_client(
                    PASS_LIST_SCROLL_POINT, -1, count=3, interval=0.05, after_sleep=0.8
                )
                continue
            badge_y, caption = target
            key = caption or f"y{badge_y}"
            visits[key] = visits.get(key, 0) + 1
            if visits[key] > PASS_MAX_VISITS:
                self.log_info(f"通行证「{key}」：点过两次全部获得红点仍在，跳过。")
                skipped[key] = "处理两次还在"
                continue
            if not self._claim_badged_pass(key, badge_y):
                return self._claim_fail(f"领取{key}")
            claimed += 1
        self.info_set("通行证数量", claimed)
        if not claimed and not skipped:
            self.log_info("通行证：左侧没有红点，没有可领的。")
        if skipped:
            left = "、".join(f"「{key}」{why}" for key, why in skipped.items())
            self.log_info(f"通行证：这些还有红点，没领：{left}。")
        if not self._leave_to_home("通行证", PASS_TITLE_KEYWORDS):
            return self._claim_fail("通行证返回主页")
        return True

    @staticmethod
    def _pass_caption_boxes(boxes: list) -> list:
        return [
            box
            for box in boxes
            if keyword_match_count(getattr(box, "name", ""), PASS_TITLE_KEYWORDS) >= 1
            and keyword_match_count(getattr(box, "name", ""), PASS_PURCHASE_KEYWORDS) == 0
        ]

    def _pass_cards(
        self, roi: tuple[int, int, int, int] = PASS_LIST_EXTENDED_ROI, wait: float = 4.0
    ) -> list[str]:
        boxes = self._wait_boxes(
            roi, "通行证列表", lambda found: bool(self._pass_caption_boxes(found)), timeout=wait
        )
        captions = [str(getattr(box, "name", "")) for box in self._pass_caption_boxes(boxes)]
        self.info_set("通行证列表", "、".join(captions) or "-")
        return captions[:PASS_MAX_CARDS]

    def _next_pass_badge(self, frame, skipped: dict[str, str]):
        """(badge y, caption) of the first badged pass not skipped, or None."""
        badges = find_red_badges(frame, PASS_BADGE_STRIP)
        self.info_set("通行证红点", ",".join(str(y) for y in badges) or "-")
        if not badges:
            return None
        boxes = self._pass_caption_boxes(
            self._roi_boxes(frame, PASS_LIST_EXTENDED_ROI, "通行证列表")
        )
        for badge_y in badges:
            caption = self._pass_caption_near(frame, boxes, badge_y)
            if (caption or f"y{badge_y}") not in skipped:
                return badge_y, caption
        return None

    @staticmethod
    def _pass_caption_near(frame, boxes: list, badge_y: int) -> str:
        """Simplified caption of the card under the badge (its nearest below)."""
        height = frame.shape[0] if frame is not None else REFERENCE_HEIGHT
        sy = REFERENCE_HEIGHT / max(1, height)
        best, best_gap = "", None
        for box in boxes:
            center = (float(box.y) + float(box.height) / 2) * sy
            gap = center - badge_y
            if 0 <= gap <= 100 and (best_gap is None or gap < best_gap):
                best, best_gap = to_simplified(str(getattr(box, "name", ""))), gap
        return best

    def _claim_badged_pass(self, key: str, badge_y: int) -> bool:
        self.info_set("当前阶段", f"打开通行证：{key}")
        card_y = badge_y + PASS_BADGE_TO_CARD_CENTER
        half_w, half_h = PASS_CARD_HALF_SIZE
        card_roi = (PASS_CARD_X - half_w, max(0, card_y - half_h), 2 * half_w, 2 * half_h)
        changed = self._click_until_changed(
            f"通行证 {key}",
            lambda: self._click_reference(PASS_CARD_X, card_y, after_sleep=0.2),
            (card_roi, PASS_CLAIM_BUTTON.roi),
            attempts=2,
            wait=1.2,
        )
        if not changed:
            # The selected card (the top one on entry) changes nothing when
            # pressed.  If the press was lost instead, the previous pass's
            # button is grey and nothing is pressed; the badge stays and the
            # card is opened again on the next look.
            self.log_info(f"通行证「{key}」：点了画面没变化，按已打开处理。")
        if not self._claim_all(key, PASS_CLAIM_BUTTON, PASS_TITLE_KEYWORDS):
            return False
        # Live 2026-10-24: the 艾瑞克 character pass and the return pass kept
        # their badge with a grey button on LEVEL; the claimable rewards were
        # finished missions on the MISSION tab, which in turn give pass EXP
        # and so new LEVEL rewards.
        self._click_reference(*PASS_MISSION_TAB_POINT, after_sleep=1.0)  # 不用确认：没切过去就是在等级页再领一次
        if not self._claim_all(f"{key}任务", PASS_CLAIM_BUTTON, PASS_TITLE_KEYWORDS):
            return False
        self._click_reference(*PASS_LEVEL_TAB_POINT, after_sleep=1.0)  # 不用确认：红点留着，下一轮再开这张
        return self._claim_all(f"{key}等级", PASS_CLAIM_BUTTON, PASS_TITLE_KEYWORDS)


class ClearPackRewardTask(_ClaimTaskBase):
    """2026-10-24: every story card cleared on 普通/困难/极难 and every 10th
    欲望之塔 floor gives 100 钻石 for free from its 通关礼包 in 付费商店.  Open
    each red-badged tab and pack and press only the 「免费」 buttons."""

    claim_log_name = "clear_pack"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "领取通关礼包"
        self.description = (
            "打开付费商店，在有红点的分页和礼包里只点「免费」，"
            "领通关剧情游戏卡/欲望之塔送的钻石（绝不点购买）。"
        )
        self.icon = FluentIcon.SHOPPING_CART

    def run_claim(self) -> bool:
        if not self._open_page_from_home("付费商店", SHOP_ENTRY_POINT, SHOP_TITLE_KEYWORDS):
            return self._claim_fail("打开付费商店")
        claimed = 0
        opened_tabs: set[int] = set()
        for _tab in range(SHOP_MAX_TABS):
            badges = [
                y
                for y in find_red_badges(self.capture_frame(), SHOP_TAB_BADGE_STRIP)
                if y not in opened_tabs
            ]
            self.info_set("付费商店分页红点", ",".join(str(y) for y in badges) or "-")
            if not badges:
                break
            badge_y = badges[0]
            # A tab's badge can outlive its last free reward (seen right after
            # a claim), so each badged tab is opened once.
            opened_tabs.add(badge_y)
            self._click_reference(SHOP_TAB_X, badge_y + SHOP_TAB_BADGE_TO_CENTER, after_sleep=1.5)  # 不用确认：接着读礼包红点
            claimed += self._claim_badged_packs()
        self.info_set("通关礼包领取", claimed)
        if claimed:
            self.log_info(f"通关礼包：点了 {claimed} 次「免费」，钻石发到邮箱。")
        else:
            self.log_info("通关礼包：没有可以免费领的。")
        if not self._leave_to_home("付费商店", SHOP_TITLE_KEYWORDS):
            return self._claim_fail("付费商店返回主页")
        return True

    def _claim_badged_packs(self) -> int:
        """Open every red-badged pack of this tab, scrolling down the list."""
        claimed = 0
        opened: set[str] = set()
        scrolls = 0
        for _step in range(SHOP_MAX_PACKS + SHOP_PACK_SCROLL_ROUNDS):
            frame = self.capture_frame()
            target = None
            for badge_y in find_red_badges(frame, SHOP_PACK_BADGE_STRIP):
                key = self._pack_caption(frame, badge_y) or f"y{badge_y}@{scrolls}"
                if key not in opened:
                    target = (badge_y, key)
                    break
            if target is None:
                if scrolls >= SHOP_PACK_SCROLL_ROUNDS:
                    break
                scrolls += 1
                self.scroll_client(
                    SHOP_PACK_SCROLL_POINT, -1, count=10, interval=0.05, after_sleep=0.8
                )
                continue
            badge_y, key = target
            opened.add(key)
            self.info_set("当前阶段", f"通关礼包：{key}")
            self._click_reference(SHOP_PACK_X, badge_y + SHOP_PACK_BADGE_TO_CENTER, after_sleep=2.0)  # 不用确认：接着等「免费」
            claimed += self._press_free_buttons(key)
        return claimed

    def _pack_caption(self, frame, badge_y: int) -> str:
        top, bottom = SHOP_PACK_CAPTION_BELOW_BADGE
        x, w = SHOP_PACK_CAPTION_X
        boxes = self._reference_boxes(frame, (x, badge_y + top, w, bottom - top), "通关礼包名")
        return to_simplified(self._boxes_text(boxes)).strip()

    @staticmethod
    def _only_free(boxes: list) -> list:
        # Exactly 「免费」: the pack contents line can read 「免费钻石500」.
        return [
            box
            for box in boxes
            if to_simplified(str(getattr(box, "name", ""))).strip() == SHOP_FREE_TEXT
        ]

    def _free_boxes(self) -> list:
        # The pack panel draws a moment after the click; wait for a 「免费」.
        boxes = self._wait_boxes(
            SHOP_FREE_ROI,
            "通关礼包免费",
            lambda found: bool(self._only_free(found)),
            timeout=3.0,
            reference=True,
        )
        return self._only_free(boxes)

    def _press_free_buttons(self, key: str) -> int:
        pressed = 0
        for _press in range(SHOP_MAX_FREE_PER_PACK):
            boxes = self._free_boxes()
            if not boxes:
                break
            box = boxes[0]
            self.log_info(f"通关礼包「{key}」：点「免费」。")
            self._click_reference(
                round(box.x + box.width / 2),
                round(box.y + box.height / 2) - SHOP_FREE_ICON_ABOVE_TEXT,
                after_sleep=2.0,
            )  # 不用确认：下一轮重读「免费」还在不在
            pressed += 1
        return pressed
