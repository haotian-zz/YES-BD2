"""Player v0.2.11 2026-10-23: 每周跑图 skipped 第11章 (回主城失败) and went on
to 第14章; the 问题摘要 showed 第14章's last screen and lines, so where 第11章
stopped could not be seen.  Also its message 「没认出小地图的≡按钮」 (no why): an area map
opened with its title unread was left open over the ≡ button."""

import inspect
import logging
import tempfile
import time
import unittest
from types import SimpleNamespace

import cv2
import numpy as np

from src.tasks import problem_report
from src.tasks.map_trade.navigator import Navigator
from tests.test_problem_report import Task


def frame(shade, width=1920, height=1080):
    return np.full((height, width, 3), shade, dtype=np.uint8)


class SkipScreenTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        problem_report.set_root(self.folder.name)
        problem_report.install_log_ring()
        self.log = logging.getLogger("ok")
        self.log.setLevel(logging.DEBUG)

    def tearDown(self):
        self.log.removeHandler(problem_report._ring)
        problem_report._ring = None
        problem_report._drop()
        problem_report._last_written.clear()
        problem_report.set_root(None)
        self.folder.cleanup()

    def shade(self, path):
        return int(cv2.imread(path).mean())

    def test_the_first_skipped_card_shows_its_own_screen_and_lines(self):
        task = Task("每周跑图")
        task.executor._frame = frame(30)  # 第14章's last screen
        with problem_report.run_scope(task) as scope:
            self.log.info("MapCollectionTask:第11章：没按到小地图的≡按钮")
            problem_report.note_skip(task, frame(200), now=time.time())
            self.log.info("MapCollectionTask:第14章：战斗区域1已完成")
            problem_report.note_skip(task, frame(90))  # a later card: the first wins
            problem_report.note_problem(task, "fail")
            scope.result = False
        [record] = problem_report.records()
        self.assertAlmostEqual(200, self.shade(record["frame_path"]), delta=2)
        texts = [line["text"] for line in record["problem"]["logs"]]
        self.assertIn("第11章：没按到小地图的≡按钮", texts)
        self.assertNotIn("第14章：战斗区域1已完成", texts)

    def test_a_card_tried_again_forgets_its_first_skip(self):
        task = Task("每周跑图")
        task.executor._frame = frame(30)
        with problem_report.run_scope(task) as scope:
            problem_report.note_skip(task, frame(200))
            problem_report.forget_skip()
            problem_report.note_skip(task, frame(120))
            problem_report.note_problem(task, "fail")
            scope.result = False
        [record] = problem_report.records()
        self.assertAlmostEqual(120, self.shade(record["frame_path"]), delta=2)

    def test_another_tasks_failure_keeps_its_own_screen(self):
        batch, maps, pvp = Task("一键完成日常"), Task("每周跑图"), Task("镜中之战")
        maps.executor = pvp.executor = batch.executor
        batch.executor._frame = frame(30)
        with problem_report.run_scope(batch):
            with problem_report.run_scope(maps):
                problem_report.note_skip(maps, frame(200))
            with problem_report.run_scope(pvp):
                problem_report.note_problem(pvp, "fail")
        [record] = problem_report.records()
        self.assertAlmostEqual(30, self.shade(record["frame_path"]), delta=2)


class AreaMapLeftOpenTest(unittest.TestCase):
    def _navigator(self, header, footer):
        task = SimpleNamespace(config={}, info_set=lambda *_a: None, sleep=lambda _s: None)
        task.clicks = []
        task.operate_click = lambda x, y, after_sleep=0.0: task.clicks.append((x, y))
        task.log_warning = lambda *_a, **_k: None
        vision = SimpleNamespace(
            capture=lambda: "frame",
            simplify=lambda text: text,
            ocr_text=lambda _f, name, **_k: footer() if name == "地图底栏" else header(),
        )
        navigator = object.__new__(Navigator)
        navigator.task = task
        navigator.vision = vision
        navigator._status = lambda *_a: None
        return navigator

    def test_a_map_known_only_by_its_footer_is_open(self):
        navigator = self._navigator(lambda: "", lambda: "世界地图 探索")
        self.assertTrue(navigator._area_map_open())
        navigator = self._navigator(lambda: "", lambda: "")
        self.assertFalse(navigator._area_map_open())

    def test_a_map_opened_with_its_title_unread_is_not_reported_closed(self):
        from src.tasks.map_trade import navigator_sandbox

        clock = iter(range(0, 1000))
        navigator = self._navigator(lambda: "罗坦", lambda: "世界地图 探索")
        original = navigator_sandbox.monotonic
        navigator_sandbox.monotonic = lambda: next(clock)
        try:
            header = navigator._open_field_map()
        finally:
            navigator_sandbox.monotonic = original
        # Not None: callers close a map they get a header for.
        self.assertEqual("罗坦", header)

    def test_close_presses_again_while_only_the_footer_shows(self):
        from src.tasks.map_trade import navigator_sandbox

        state = {"open": 3}

        def footer():
            state["open"] -= 1
            return "世界地图" if state["open"] > 0 else ""

        clock = iter(range(0, 1000))
        navigator = self._navigator(lambda: "", footer)
        original = navigator_sandbox.monotonic
        navigator_sandbox.monotonic = lambda: next(clock) * 0.1
        try:
            navigator._close_field_map()
        finally:
            navigator_sandbox.monotonic = original
        self.assertEqual(2, len(navigator.task.clicks))  # the press and one more

    def test_a_missed_menu_button_says_why(self):
        """Leo 2026-10-24 「錯誤要寫原因 不要寫讀不到」."""
        for map_open, why in (
            (True, "区域地图按返回也关不掉，挡住了≡按钮"),
            (False, "画面上看不到地图界面的按键提示"),
        ):
            with self.subTest(map_open=map_open):
                navigator = self._navigator(lambda: "", lambda: "")
                navigator.task.log_warning = lambda *_a, **_k: None
                navigator.task.log_info = lambda *_a, **_k: None
                navigator.vision.click_template = lambda *_a, **_k: False
                navigator.vision.match = lambda *_a: None
                navigator.vision.passes = lambda *_a: False
                navigator.classify = lambda _frame: None
                navigator._area_map_open = lambda: map_open
                navigator._close_field_map = lambda: None
                navigator._in_hunting_ground = lambda: False
                self.assertIsNone(navigator._travel_via_nav_menu("狩猎场", "艾琳"))
                self.assertTrue(navigator._nav_failure.startswith("没按到小地图的≡按钮："))
                self.assertIn(why, navigator._nav_failure)

    def test_navigator_bases_share_no_method_name(self):
        """v0.2.11: the 跑图 _area_map_open() shadowed the 跑商 one that took
        seconds, and every 跑商 walk over the area map raised a TypeError."""
        owners = {}
        for base in Navigator.__mro__[1:]:
            if base is object:
                continue
            for name, value in vars(base).items():
                if inspect.isfunction(value) and not name.startswith("__"):
                    owners.setdefault(name, []).append(base.__name__)
        shared = {name: where for name, where in owners.items() if len(where) > 1}
        self.assertEqual({}, shared)


if __name__ == "__main__":
    unittest.main()
