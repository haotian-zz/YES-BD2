"""格鲁TALK 相遇 (user 2026-11-06): the three free encounters of the day.

「每天有三次机会和三个人发生事件，只选择等级小于10的…等级越高越优先选择」.
主页 → 格鲁TALK → the chat tab: every person's level is read off the pink
heart of their row, people below 10 are taken highest level first, and for
each one the chat is played (the reply under 「发送消息」 pressed) until
its 「进行相遇事件」 card; the encounter is confirmed only while the dialog
shows a free count left and nothing paid, its story skipped (F2 → 确认),
and the level-up reward (50 钻石 a level) and picture closed.  The ⊕ that
buys more encounters and 「主界面设置」 on the picture are never pressed.
The screens are in glu_talk/screen.py.
"""

from __future__ import annotations

from time import monotonic

from qfluentwidgets import FluentIcon

from src.tasks import run_report
from src.tasks.glu_talk import screen
from src.tasks.recovery import recover_to_home
from src.tasks.RewardClaimTasks import _ClaimTaskBase
from src.utils.ocr_utils import keyword_match_count, normalize_ocr_text
from src.utils.press_confirm import wait_for

LABEL = "格鲁TALK"
LEVEL_KEY = "只选等级低于"
PROBE_KEY = "_试跑只读列表"
OPEN_ATTEMPTS = 3
LIST_SCROLL_ROUNDS = 8
# A chat whose card never shows (no next episode yet, a read that keeps
# failing) is left after this long or this many replies.
CHAT_SECONDS = 90.0
CHAT_REPLIES_MAX = 30
CHAT_POLL_SECONDS = 1.0
SCENE_SECONDS = 90.0
AFTER_SCENE_SECONDS = 40.0
KEY_F2 = 0x71
KEY_ESC = 0x1B


class GluTalkTask(_ClaimTaskBase):
    claim_log_name = "glu_talk"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "格鲁TALK相遇"
        self.description = (
            "主页 → 格鲁TALK，用掉每天免费的 3 次相遇：只选等级低于 10 的人，"
            "等级高的先；聊天选第一个回复，跳过相遇剧情（每升一级 50 钻石）。"
            "绝不点购买相遇次数。"
        )
        self.icon = FluentIcon.CHAT
        self.default_config[LEVEL_KEY] = screen.LEVEL_MAX
        self.config_description[LEVEL_KEY] = "只和等级低于这个数的人相遇（默认 10）。"
        # Hidden: open the chat tab, read and log every row, close (no encounter).
        self.default_config[PROBE_KEY] = False

    # -- flow -------------------------------------------------------------------------

    def run_claim(self) -> bool:
        if not self._open_window():
            return self._claim_fail("打开格鲁TALK")
        left = self._remaining()
        self.info_set("今日的剩余相遇", "-" if left is None else left)
        if bool(self.config.get(PROBE_KEY, False)):
            return self._probe_list(left)
        if left == 0:
            self.log_info(f"{LABEL}：今天的相遇次数已经用完。")
            return self._close() or self._claim_fail("格鲁TALK返回主页")
        if not self._open_chats():
            self._close()
            return self._claim_fail("打开格鲁TALK消息")
        rows = self._read_rows()
        limit = self._level_limit()
        targets = screen.choose(rows, limit)
        self.info_set("格鲁TALK列表", "、".join(f"{r.name}{r.level}" for r in rows)[:300] or "-")
        self.info_set("格鲁TALK候选", "、".join(f"{r.name}{r.level}" for r in targets) or "-")
        if not rows:
            self._note_why("格鲁TALK消息列表上没读到任何人")
            self._save_flow_diagnostic("glu_talk_list_unread")
            self._close()
            return self._claim_fail("读取格鲁TALK列表")
        done: list[str] = []
        problems: list[str] = []
        for row in targets:
            if left is not None and left <= 0:
                break
            outcome = self._encounter(row)
            if outcome == "done":
                done.append(f"{row.name}（{row.level}→{row.level + 1}）")
                left = self._remaining()
                self.info_set("今日的剩余相遇", "-" if left is None else left)
            elif outcome == "used up":
                left = 0
            elif outcome:
                problems.append(f"{row.name}：{outcome}")
                if not self._window_open():
                    break
        if done:
            note = f"格鲁TALK 相遇：{'、'.join(done)}"
            self.log_info(f"{LABEL}：{note}。")
            run_report.add_current_note(note)
        elif not targets:
            self.log_info(f"{LABEL}：列表上没有等级低于 {limit} 的人，不相遇。")
        if not self._close():
            return self._claim_fail("格鲁TALK返回主页")
        if problems and not done:
            self._note_why("；".join(problems[:3]))
            return self._claim_fail("相遇")
        if problems:
            self.log_info(f"{LABEL}：没做成的：{'；'.join(problems[:3])}。")
        return True

    def _probe_list(self, left: int | None) -> bool:
        if not self._open_chats():
            self._close()
            return self._claim_fail("打开格鲁TALK消息")
        rows = self._read_rows()
        targets = screen.choose(rows, self._level_limit())
        self.log_info(
            f"{LABEL}试跑：剩余相遇 {left}；列表 {'、'.join(f'{r.name}={r.level}' for r in rows) or '-'}；"
            f"会选 {'、'.join(r.name for r in targets) or '-'}。"
        )
        return self._close() or self._claim_fail("格鲁TALK返回主页")

    def _level_limit(self) -> int:
        try:
            return max(1, min(screen.LEVEL_MAX, int(self.config.get(LEVEL_KEY, screen.LEVEL_MAX))))
        except (TypeError, ValueError):
            return screen.LEVEL_MAX

    # -- window -----------------------------------------------------------------------

    def _header_text(self, frame=None) -> str:
        frame = self.capture_frame() if frame is None else frame
        text = self._boxes_text(self._reference_boxes(frame, screen.HEADER_ROI, "格鲁TALK标题"))
        self.info_set("格鲁TALK标题 OCR", text or "-")
        return text

    def _window_open(self, frame=None) -> bool:
        return keyword_match_count(self._header_text(frame), screen.WINDOW_WORDS) >= 1

    def _remaining_read(self) -> tuple[int] | None:
        """(encounters left,) — a tuple, so 0 counts as read."""
        left = screen.read_remaining(self._header_text())
        return None if left is None else (left,)

    def _remaining(self) -> int | None:
        read = self.look_again(self._remaining_read, "今日的剩余相遇", popups=False)
        return read[0] if read else None

    def _home_entry(self) -> tuple[int, int]:
        """The 格鲁TALK icon: above the label read on 主页, else its usual place."""
        boxes = self._reference_boxes(self.capture_frame(), screen.HOME_ENTRY_ROI, "主页格鲁TALK入口")
        box = self._box_with(boxes, screen.HOME_ENTRY_WORDS)
        if box is None:
            return screen.ENTRY_POINT
        return round(box.x + box.width / 2), round(box.y - screen.HOME_ICON_ABOVE_LABEL)

    def _open_window(self) -> bool:
        for attempt in range(1, OPEN_ATTEMPTS + 1):
            if not self._wait_for_home_confirmation(f"{LABEL}入口前主页确认", timeout=3.0):
                self.log_info(f"{LABEL}：不在主页，先回主页。")
                if not recover_to_home(self):
                    self._note_why("不在主页，也没能回到主页，所以没点格鲁TALK")
                    return False
                continue
            self._sleep_after_recognition()
            point = self._home_entry()
            outcome = self.press_and_confirm(
                f"{LABEL}：打开",
                lambda: self._click_reference(*point, after_sleep=0.8),
                self._window_open,
                still_before=lambda: self._home_confirmation_signals(
                    self.capture_frame(), f"{LABEL}入口点击后"
                )[0],
                timeout=4.0,
            )
            if outcome:
                return True
            self.log_info(f"{LABEL}：第{attempt}次没打开格鲁TALK。")
            self._clear_home_popup(LABEL)
        self._note_why("点了主页的格鲁TALK，没看到格鲁TALK视窗")
        self._save_flow_diagnostic("glu_talk_window_not_open")
        return False

    def _chats_shown(self) -> bool:
        boxes = self._reference_boxes(self.capture_frame(), screen.LIST_HEADER_ROI, "格鲁TALK消息页签")
        return keyword_match_count(self._boxes_text(boxes), screen.CHATS_TAB_WORDS) >= 1

    def _open_chats(self) -> bool:
        if self._chats_shown():
            return True
        outcome = self.press_and_confirm(
            f"{LABEL}：消息页签",
            lambda: self._click_reference(*screen.CHATS_TAB_POINT, after_sleep=0.5),
            self._chats_shown,
            still_before=self._window_open,
        )
        if not outcome:
            self._note_why("点了格鲁TALK左边的消息页签，没看到「未读消息」")
        return bool(outcome)

    def _close(self) -> bool:
        # The window first: the home check on the dimmed 主页 behind it reads
        # a login notice and taps beside it (live 2026-11-06 18:29).
        if self._window_open():
            self.press_and_confirm(
                f"{LABEL}：关闭",
                lambda: self._click_reference(*screen.CLOSE_POINT, after_sleep=0.8),
                lambda: not self._window_open(),
                still_before=self._window_open,
            )
        if self._wait_for_home_confirmation(f"{LABEL}关闭后", timeout=5.0):
            return True
        self.log_info(f"{LABEL}：关了视窗没认出主页，改用通用回主页。")
        return bool(recover_to_home(self))

    # -- list -------------------------------------------------------------------------

    def _rows(self) -> list[screen.Row]:
        frame = self.capture_frame()
        reference = screen.to_reference(frame)
        hearts = screen.find_hearts(reference)
        if not hearts:
            return []
        boxes = self._reference_boxes(frame, screen.LIST_ROI, "格鲁TALK列表")
        rows = []
        for heart in hearts:
            centre_y = heart[1] + heart[3] // 2
            name = screen.row_name(boxes, centre_y)
            if not name:
                continue
            digit = self.ocr(
                frame=screen.heart_digit_image(reference, heart),
                threshold=0.3,
                target_height=0,
                log=False,
                name="格鲁TALK等级",
                reread=False,
            )
            level = screen.read_level("".join(str(getattr(b, "name", "")) for b in digit or []))
            rows.append(screen.Row(name, level, centre_y))
        return rows

    def _scroll_list(self, notches: int) -> None:
        self.scroll_client(screen.LIST_SCROLL_POINT, notches, count=3, interval=0.05, after_sleep=0.8)

    def _read_rows(self) -> list[screen.Row]:
        """Every row, scrolling down while new names show; the list back on top."""
        rows = wait_for(self._rows, 4.0, sleep=self.sleep) or []
        known = {row.key for row in rows}
        for _round in range(LIST_SCROLL_ROUNDS):
            self._scroll_list(-1)
            more = [row for row in self._rows() if row.key not in known]
            if not more:
                break
            known.update(row.key for row in more)
            rows += more
        unread = [row.name for row in rows if row.level is None]
        if unread:
            self.log_info(f"{LABEL}：没读到等级的人（不选）：{'、'.join(unread)}。")
        self._list_to_top()
        return rows

    def _list_to_top(self) -> None:
        self.scroll_client(screen.LIST_SCROLL_POINT, 1, count=3 * LIST_SCROLL_ROUNDS, interval=0.03, after_sleep=0.8)

    def _find_row(self, row: screen.Row) -> screen.Row | None:
        found = next((r for r in self._rows() if r.key == row.key), None)
        if found is not None:
            return found
        self._list_to_top()
        for _round in range(LIST_SCROLL_ROUNDS + 1):
            found = next((r for r in self._rows() if r.key == row.key), None)
            if found is not None:
                return found
            self._scroll_list(-1)
        return None

    # -- one encounter ----------------------------------------------------------------

    def _chat_boxes(self) -> list:
        return self._reference_boxes(self.capture_frame(), screen.CHAT_ROI, "格鲁TALK聊天")

    def _chat_names(self, boxes: list, row: screen.Row) -> bool:
        key = row.key[-3:] if len(row.key) > 3 else row.key
        return any(key and key in normalize_ocr_text(getattr(b, "name", "")) for b in boxes)

    def _encounter(self, row: screen.Row) -> str:
        """「done」, 「used up」 or why not (player words)."""
        self.info_set("当前阶段", f"{LABEL}：{row.name}")
        target = self._find_row(row)
        if target is None:
            return "列表上找不到这个人"
        opened = self.press_and_confirm(
            f"{LABEL}：打开和{row.name}的聊天",
            lambda: self._click_reference(screen.ROW_PRESS_X, target.y, after_sleep=0.8),
            lambda: self._chat_names(self._chat_boxes(), row),
            still_before=self._window_open,
        )
        if not opened:
            return "点了没打开聊天"
        card = self._play_chat(row)
        if card is None:
            return "聊天里没等到「进行相遇事件」"
        return self._start_encounter(row, card)

    def _play_chat(self, row: screen.Row):
        """Press the replies until the 进行相遇事件 card; its box, else None."""
        started = monotonic()  # 自己等：聊天一句句来，按回复数和总时长收尾
        replies = 0
        last_reply = ""
        while replies <= CHAT_REPLIES_MAX:
            step = screen.chat_step(self._chat_boxes())
            if step.kind == "start":
                return step.box
            if step.kind == "done":
                self.log_info(f"{LABEL}：{row.name}的相遇事件已经完成，没有新的。")
                return None
            if step.kind == "reply":
                text = str(getattr(step.box, "name", ""))
                if text == last_reply:
                    # The same reply still up a moment after its press: let
                    # the chat move on before pressing it again.
                    self.sleep(CHAT_POLL_SECONDS)
                    step = screen.chat_step(self._chat_boxes())
                    if step.kind != "reply":
                        continue
                    text = str(getattr(step.box, "name", ""))
                self.log_info(f"{LABEL}：{row.name}的聊天回复「{text}」。")
                self._click_reference_box(step.box, after_sleep=1.0)  # 不用确认：下一轮读聊天
                replies += 1
                last_reply = text
            if monotonic() - started >= CHAT_SECONDS:
                break
            self.sleep(CHAT_POLL_SECONDS)
        self._save_flow_diagnostic("glu_talk_chat_no_card")
        return None

    def _dialog_text(self) -> str:
        boxes = self._reference_boxes(self.capture_frame(), screen.DIALOG_ROI, "相遇事件确认")
        return self._boxes_text(boxes)

    def _dialog_shown(self) -> bool:
        return keyword_match_count(self._dialog_text(), screen.DIALOG_WORDS) >= 1

    def _start_encounter(self, row: screen.Row, card) -> str:
        shown = self.press_and_confirm(
            f"{LABEL}：{row.name} 进行相遇事件",
            lambda: self._click_reference_box(card, after_sleep=0.8),
            self._dialog_shown,
            still_before=lambda: screen.chat_step(self._chat_boxes()).kind == "start",
        )
        if not shown:
            return "点了「进行相遇事件」没出确认框"
        text = self._dialog_text()
        boxes = self._reference_boxes(self.capture_frame(), screen.DIALOG_ROI, "相遇事件确认")
        if not screen.dialog_is_free(text):
            self.log_info(f"{LABEL}：确认框不是免费次数（{text}），按取消。")
            cancel = self._box_with(boxes, ("取消",))
            if cancel is not None:
                self._click_reference_box(cancel, after_sleep=0.8)  # 不用确认：之后看视窗
            else:
                self._send_game_key(KEY_ESC, 0.08)
            return "used up" if (screen.read_dialog_count(text) or 0) < 1 else "确认框里有付费字样，没确认"
        confirm = self._box_with(boxes, ("确认",))
        if confirm is None:
            return "确认框上没读到「确认」"
        # Re-pressed only while the same dialog is still up: one dialog can
        # only start one encounter.
        started = self.press_and_confirm(
            f"{LABEL}：{row.name} 确认相遇",
            lambda: self._click_reference_box(confirm, after_sleep=1.0),
            lambda: not self._dialog_shown(),
            still_before=self._dialog_shown,
        )
        if not started:
            return "按了确认，确认框还在"
        self.log_info(f"{LABEL}：和{row.name}（{row.level}级）开始相遇事件。")
        # The window stays up a moment before the scene loads: it showing
        # right after 确认 is not the scene being over.
        if not wait_for(lambda: not self._window_open(), 10.0, sleep=self.sleep):
            self.log_info(f"{LABEL}：按了确认，格鲁TALK视窗一直在，没进相遇剧情。")
            return "按了确认没进相遇剧情"
        if not self._skip_scene(row):
            return "相遇剧情没能跳过"
        if not self._after_scene(row):
            return "相遇后没回到格鲁TALK"
        return "done"

    def _screen_text(self, roi=None) -> str:
        return self._boxes_text(self._reference_boxes(self.capture_frame(), roi, "格鲁TALK画面"))

    def _skip_scene(self, row: screen.Row) -> bool:
        """F2 / the skip button, then 确认 on 「跳过对话」; taps if it never shows."""
        started = monotonic()  # 自己等：剧情载入后才有跳过，F2 和跳过键轮流按
        pressed_key = False
        while monotonic() - started < SCENE_SECONDS:
            text = self._screen_text(screen.SKIP_DIALOG_ROI)
            if keyword_match_count(text, screen.SKIP_DIALOG_WORDS) >= 1:
                boxes = self._reference_boxes(self.capture_frame(), screen.SKIP_DIALOG_ROI, "跳过对话")
                confirm = self._box_with(boxes, ("确认",))
                point = (
                    (round(confirm.x + confirm.width / 2), round(confirm.y + confirm.height / 2))
                    if confirm is not None
                    else (1044, 780)
                )
                self.press_and_confirm(
                    f"{LABEL}：跳过对话 确认",
                    lambda: self._click_reference(*point, after_sleep=1.0),
                    lambda: keyword_match_count(
                        self._screen_text(screen.SKIP_DIALOG_ROI), screen.SKIP_DIALOG_WORDS
                    ) < 1,
                    still_before=lambda: keyword_match_count(
                        self._screen_text(screen.SKIP_DIALOG_ROI), screen.SKIP_DIALOG_WORDS
                    ) >= 1,
                )
                return True
            if self._scene_over():
                return True
            if not pressed_key and self._send_game_key(KEY_F2, 0.08):
                pressed_key = True
            else:
                self._click_reference(*screen.SKIP_POINT, after_sleep=0.3)  # 不用确认：下一轮看跳过对话
                pressed_key = False
            self.sleep(1.2)
        self._save_flow_diagnostic("glu_talk_scene_not_skipped")
        return False

    def _scene_over(self) -> bool:
        text = self._screen_text()
        return (
            keyword_match_count(text, screen.REWARD_WORDS + screen.EFFECT_WORDS) >= 1
            or self._window_open()
        )

    def _after_scene(self, row: screen.Row) -> bool:
        """Close 获得好感度奖励 and the 好感度特效 picture until the window shows."""
        started = monotonic()  # 自己等：奖励和特效画面一个个关，直到视窗回来
        while monotonic() - started < AFTER_SCENE_SECONDS:
            frame = self.capture_frame()
            if self._window_open(frame):
                return True
            text = self._boxes_text(self._reference_boxes(frame, None, "相遇奖励"))
            if keyword_match_count(text, screen.REWARD_WORDS) >= 1:
                self.log_info(f"{LABEL}：{row.name}升级奖励（{text[:40]}），点空白处关闭。")
                self._click_reference(*screen.REWARD_TAP_POINT, after_sleep=1.5)  # 不用确认：下一轮看画面
                continue
            if keyword_match_count(text, screen.EFFECT_WORDS) >= 1:
                # Never 主界面设置 (bottom right): the back arrow top left.  The
                # first press may only end the picture's fade-in; the next
                # round presses again.  No Esc: on the window it closes GLU TALK.
                self._click_reference(*screen.EFFECT_BACK_POINT, after_sleep=1.5)  # 不用确认：下一轮看画面
                continue
            self.sleep(1.0)
        self._save_flow_diagnostic("glu_talk_after_scene")
        return False
