import threading
import unittest
from unittest.mock import patch

import pywintypes

from src.interaction.BD2Interaction import BD2Interaction, _set_cursor


def make_interaction():
    """Build a BD2Interaction without running its device ``__init__``."""
    interaction = object.__new__(BD2Interaction)
    interaction._input_lock = threading.RLock()
    interaction._operating = False
    interaction.cursor_position = (1, 2)
    calls = []
    interaction._restore_cursor = lambda: calls.append("restore_cursor")
    interaction.block_input = lambda: calls.append("block_input")
    interaction.unblock_input = lambda: calls.append("unblock_input")
    return interaction, calls


class BD2InteractionOperateTest(unittest.TestCase):
    def test_operate_reraises_callback_exception_and_cleans_up(self):
        interaction, calls = make_interaction()
        error = ValueError("boom")

        def failing_callback():
            raise error

        with patch(
            "src.interaction.BD2Interaction.GetCursorPos",
            return_value=(7, 8),
        ):
            with self.assertRaises(ValueError) as caught:
                interaction.operate(failing_callback, block=True)

        self.assertIs(error, caught.exception)
        self.assertFalse(interaction._operating)
        self.assertIn("block_input", calls)
        self.assertIn("restore_cursor", calls)
        self.assertIn("unblock_input", calls)

    def test_operate_returns_callback_result_and_cleans_up(self):
        interaction, calls = make_interaction()

        with patch(
            "src.interaction.BD2Interaction.GetCursorPos",
            return_value=(7, 8),
        ) as get_cursor_pos:
            result = interaction.operate(lambda: 42, block=True)

        self.assertEqual(42, result)
        self.assertFalse(interaction._operating)
        get_cursor_pos.assert_called_once_with()
        self.assertIn("block_input", calls)
        self.assertIn("restore_cursor", calls)
        self.assertIn("unblock_input", calls)

    def test_nested_operate_keeps_outer_layer_state_isolated(self):
        interaction, calls = make_interaction()
        states_after_inner = []

        def outer_callback():
            inner_result = interaction.operate(lambda: "inner", block=True)
            states_after_inner.append((inner_result, interaction._operating))
            raise RuntimeError("outer boom")

        with patch(
            "src.interaction.BD2Interaction.GetCursorPos",
            return_value=(7, 8),
        ) as get_cursor_pos:
            with self.assertRaises(RuntimeError):
                interaction.operate(outer_callback)

        self.assertEqual([("inner", True)], states_after_inner)
        self.assertFalse(interaction._operating)
        get_cursor_pos.assert_called_once_with()
        self.assertEqual(1, calls.count("restore_cursor"))


class SetCursorRetryTest(unittest.TestCase):
    """A fresh RDP logon briefly refused SetCursorPos (2026-11-18); the click
    waits for it instead of ending the run."""

    def test_retries_until_the_cursor_moves(self):
        failure = pywintypes.error(0, "SetCursorPos", "No error message is available")
        with patch(
            "src.interaction.BD2Interaction.SetCursorPos",
            side_effect=[failure, failure, None],
        ) as set_cursor_pos, patch("src.interaction.BD2Interaction.time.sleep") as sleep:
            _set_cursor((10, 20))

        self.assertEqual(3, set_cursor_pos.call_count)
        set_cursor_pos.assert_called_with((10, 20))
        self.assertEqual(2, sleep.call_count)

    def test_raises_once_the_retry_window_is_over(self):
        failure = pywintypes.error(0, "SetCursorPos", "No error message is available")
        with patch(
            "src.interaction.BD2Interaction.SetCursorPos",
            side_effect=failure,
        ) as set_cursor_pos, patch(
            "src.interaction.BD2Interaction.time.monotonic",
            side_effect=[0.0, 1.0, 31.0],
        ), patch("src.interaction.BD2Interaction.time.sleep"):
            with self.assertRaises(pywintypes.error) as caught:
                _set_cursor((10, 20))

        self.assertIs(failure, caught.exception)
        self.assertEqual(2, set_cursor_pos.call_count)

    def test_a_stop_is_not_retried(self):
        stop = RuntimeError("stopped")
        with patch(
            "src.interaction.BD2Interaction.SetCursorPos", side_effect=stop
        ) as set_cursor_pos, patch("src.interaction.BD2Interaction.time.sleep") as sleep:
            with self.assertRaises(RuntimeError):
                _set_cursor((10, 20))

        set_cursor_pos.assert_called_once_with((10, 20))
        sleep.assert_not_called()

    def test_first_success_needs_no_retry(self):
        with patch("src.interaction.BD2Interaction.SetCursorPos") as set_cursor_pos, patch(
            "src.interaction.BD2Interaction.time.sleep"
        ) as sleep:
            _set_cursor((3, 4))

        set_cursor_pos.assert_called_once_with((3, 4))
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
