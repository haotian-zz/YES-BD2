"""When none of the chosen dishes can be cooked, cook the first bright dish
for the cooking skill's EXP (user 2026-10-24; live 进阶 list the same day)."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import cv2
import numpy as np

from src.tasks.map_trade import trader_cooking
from src.tasks.map_trade.trader import Trader
from src.tasks.map_trade.trader_cooking import CookingRecipeOutcome, bright_recipe_cells

GRID = Path(__file__).parent / "fixtures" / "map_trade" / "cooking" / "list_advanced_grid.png"


def _list_frame(scale=1):
    """The live 进阶 list (grid cut at x 730, y 120) back on a 1080p frame."""
    frame = np.zeros((1080, 1920, 3), np.uint8)
    grid = cv2.imread(str(GRID))
    frame[120:120 + grid.shape[0], 730:730 + grid.shape[1]] = grid
    if scale != 1:
        frame = cv2.resize(frame, (1920 * scale // 3, 1080 * scale // 3), interpolation=cv2.INTER_LINEAR)
    return frame


# Live: row 1 has cards 1, 2, 4, 5, 7, 8 bright; row 2 cards 1 and 2.
LIVE_BRIGHT = [(797, 188), (923, 188), (1175, 188), (1301, 188), (1553, 188), (1679, 188), (797, 314), (923, 314)]


class BrightRecipeCellsTest(unittest.TestCase):
    def test_the_live_advanced_list(self):
        self.assertEqual(LIVE_BRIGHT, bright_recipe_cells(_list_frame()))

    def test_at_2k(self):
        self.assertEqual(LIVE_BRIGHT, bright_recipe_cells(_list_frame(scale=4)))

    def test_an_all_grey_list_has_none(self):
        self.assertEqual([], bright_recipe_cells(np.full((1080, 1920, 3), 60, np.uint8)))


class _Task:
    def __init__(self, config):
        self.config = config
        self.logs = []

    def log_info(self, message, **_kwargs):
        self.logs.append(message)

    log_warning = log_info


def _trader(config, outcomes):
    trader = object.__new__(Trader)
    trader.task = _Task(config)
    trader._status = lambda *_a: None
    trader._selected_cooking_recipes = lambda: tuple(outcomes)
    trader._enter_cooking_list = lambda: True
    trader._cook_one_recipe = lambda recipe: outcomes[recipe]
    trader._leave_cooking_to_q_sp6 = lambda: True
    trader._restore_skill_group = lambda **_k: None
    trader.practiced = []
    trader._practice_cooking = lambda count: trader.practiced.append(count) or True
    return trader


def _run(trader):
    names = {name: SimpleNamespace(file_name=name) for name in trader._selected_cooking_recipes()}
    with mock.patch.dict(trader_cooking.COOKING_RECIPE_SPECS, names):
        with mock.patch.object(trader_cooking.Path, "is_file", lambda _self: True):
            return trader.run_cooking()


class PracticeWhenNothingCookedTest(unittest.TestCase):
    def test_nothing_cookable_practices_the_default_count(self):
        trader = _trader({}, {"a": CookingRecipeOutcome.ABSENT, "b": CookingRecipeOutcome.UNAVAILABLE})
        self.assertTrue(_run(trader))
        self.assertEqual([50], trader.practiced)

    def test_a_cooked_dish_means_no_practice(self):
        trader = _trader({}, {"a": CookingRecipeOutcome.ABSENT, "b": CookingRecipeOutcome.COOKED})
        _run(trader)
        self.assertEqual([], trader.practiced)

    def test_zero_turns_it_off(self):
        trader = _trader({"练料理份数": 0}, {"a": CookingRecipeOutcome.ABSENT})
        _run(trader)
        self.assertEqual([], trader.practiced)

    def test_a_failed_practice_fails_the_cooking(self):
        trader = _trader({"练料理份数": 20}, {"a": CookingRecipeOutcome.ABSENT})
        trader._practice_cooking = lambda count: False
        self.assertFalse(_run(trader))


if __name__ == "__main__":
    unittest.main()
