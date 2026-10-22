"""Leo 2026-10-14: a press that most likely took (icon greyed, only the count
or toast unread) is reported as 「没能确认」 and does not fail the run."""

import unittest
from types import SimpleNamespace

from src.tasks.map_trade.collector import Collector
from src.tasks.map_trade.collector_skills import SkillExecutionResult
from src.tasks.map_trade.models import CollectionResult


def _collector():
    collector = object.__new__(Collector)
    collector.task = SimpleNamespace(log_warning=lambda *_a, **_k: None)
    collector._skipped_cards = []
    collector._skill_skips = {}
    collector._unconfirmed_cards = set()
    collector._record_skill_failure = lambda *_a: None
    collector._skip_card = lambda card, _why, _done: collector._skipped_cards.append(card)
    return collector


CARD = SimpleNamespace(card_id="Q_cp1", label="角色卡1")


class UnconfirmedSkipTest(unittest.TestCase):
    def test_a_greyed_icon_with_an_unread_count_does_not_fail_the_run(self):
        collector = _collector()
        message = "压制执行证据不一致：count=10/75->待对账, icon=available->used, feedback=unknown"
        collector._skip_after_skill_failure(CARD, "战斗区域1", SkillExecutionResult(False, message=message), 0)
        result = collector._with_skipped_cards(CollectionResult(True, message="完成"))
        self.assertTrue(result.success)
        self.assertIn("可能已按上但没能确认", result.message)

    def test_a_press_that_surely_failed_still_fails(self):
        collector = _collector()
        message = "压制执行证据不一致：count=10/75->10/75, icon=available->available, feedback=unknown"
        collector._skip_after_skill_failure(CARD, "战斗区域1", SkillExecutionResult(False, message=message), 0)
        result = collector._with_skipped_cards(CollectionResult(True, message="完成"))
        self.assertFalse(result.success)



class EmptySkillBarStopTest(unittest.TestCase):
    """bd2 session 2026-10-22: no group held a collection skill, and every
    card was skipped and run again; two such cards now end the run."""

    def _fail(self, collector, card):
        collector._skill_bar_lacked_skills = True
        return collector._skip_after_skill_failure(
            card, "主城区探查", SkillExecutionResult(False, message="未确认采集技能栏"), 0
        )

    def test_two_cards_without_any_collection_skill_stop_the_run(self):
        collector = _collector()
        warnings = []
        collector.task = SimpleNamespace(log_warning=lambda message, **_k: warnings.append(message))
        collector._cards_lacking_skills = set()

        self.assertIsNone(self._fail(collector, CARD))
        self.assertIsNone(self._fail(collector, CARD))  # the same card run again
        result = self._fail(collector, SimpleNamespace(card_id="Q_cp2", label="角色卡2"))

        self.assertIsInstance(result, CollectionResult)
        self.assertFalse(result.success)
        self.assertIn("技能栏里没装采集技能", result.message)
        self.assertTrue(any("技能栏里没装采集技能" in message for message in warnings))

    def test_a_bar_that_shows_some_skill_never_stops_the_run(self):
        collector = _collector()
        collector._cards_lacking_skills = set()
        for card_id in ("Q_cp1", "Q_cp2", "Q_cp3"):
            result = collector._skip_after_skill_failure(
                SimpleNamespace(card_id=card_id, label=card_id),
                "主城区探查",
                SkillExecutionResult(False, message="未确认采集技能栏"),
                0,
            )
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
