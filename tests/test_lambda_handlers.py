"""Tests for all intent handlers in lambda_function.py."""

from datetime import datetime, timedelta

import lambda_function


# ---------------------------------------------------------------------------
# LaunchRequestHandler
# ---------------------------------------------------------------------------

class TestLaunchRequestHandler:
    def test_returns_welcome_message(self, mock_handler_input):
        hi = mock_handler_input(request_type="LaunchRequest")
        handler = lambda_function.LaunchRequestHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "Welcome" in spoken
        assert "todays guest worlds" in spoken.lower() or "today" in spoken.lower()


# ---------------------------------------------------------------------------
# TodaysWorldIntentHandler
# ---------------------------------------------------------------------------

class TestTodaysWorldIntentHandler:
    def test_mid_month(self, mock_handler_input, set_lambda_globals, world_list):
        set_lambda_globals(dayNumber=5, day=5, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="TodaysWorldIntent")
        handler = lambda_function.TodaysWorldIntentHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert world_list[5] in spoken
        assert "Todays Guest Worlds" in spoken


# ---------------------------------------------------------------------------
# TomorrowsWorldIntentHandler
# ---------------------------------------------------------------------------

class TestTomorrowsWorldIntentHandler:
    def test_mid_month(self, mock_handler_input, set_lambda_globals, world_list):
        set_lambda_globals(dayNumber=10, day=10, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="TomorrowsWorldIntent")
        handler = lambda_function.TomorrowsWorldIntentHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert world_list[11] in spoken
        assert "Tomorrow" in spoken

    def test_end_of_month(self, mock_handler_input, set_lambda_globals, world_list):
        set_lambda_globals(dayNumber=31, day=31, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="TomorrowsWorldIntent")
        handler = lambda_function.TomorrowsWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "don't know next month" in spoken
        assert world_list[31] in spoken

    def test_day_before_last(self, mock_handler_input, set_lambda_globals, world_list):
        # dayNumber + 1 == lastDayOfMonth → still within bounds (< lastDayOfMonth is false when ==)
        set_lambda_globals(dayNumber=30, day=30, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="TomorrowsWorldIntent")
        handler = lambda_function.TomorrowsWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert world_list[31] in spoken


# ---------------------------------------------------------------------------
# WhenWorldIntentHandler
# ---------------------------------------------------------------------------

class TestWhenWorldIntentHandler:
    def test_watopia_always_available(self, mock_handler_input, set_lambda_globals, world_list):
        set_lambda_globals(dayNumber=5, day=5, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="WhenWorldIntent", slot_value="Watopia")
        handler = lambda_function.WhenWorldIntentHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "Watopia" in spoken
        assert "every day" in spoken

    def test_world_available_today(self, mock_handler_input, set_lambda_globals, world_list):
        # Day 3 has "Yorkshire and Innsbruck"
        set_lambda_globals(dayNumber=3, day=3, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="WhenWorldIntent", slot_value="Yorkshire")
        handler = lambda_function.WhenWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "available now" in spoken

    def test_world_available_tomorrow(self, mock_handler_input, set_lambda_globals, world_list):
        # Day 2 has "paris", day 3 has "Yorkshire and Innsbruck"
        set_lambda_globals(dayNumber=2, day=2, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="WhenWorldIntent", slot_value="Yorkshire")
        handler = lambda_function.WhenWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "available tomorrow" in spoken

    def test_world_available_in_n_days(self, mock_handler_input, set_lambda_globals, world_list):
        # Day 1 = paris, Yorkshire first appears on day 3 → 2 days away
        set_lambda_globals(dayNumber=1, day=1, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="WhenWorldIntent", slot_value="Yorkshire")
        handler = lambda_function.WhenWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "2 days from now" in spoken

    def test_world_not_found_this_month(self, mock_handler_input, set_lambda_globals, world_list):
        # Ask for London starting from day 28 — London doesn't appear after day 24
        set_lambda_globals(dayNumber=28, day=28, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="WhenWorldIntent", slot_value="London")
        handler = lambda_function.WhenWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "next month" in spoken

    def test_case_insensitive_match(self, mock_handler_input, set_lambda_globals, world_list):
        # "new york" should match "New York and Richmond" on day 10
        set_lambda_globals(dayNumber=10, day=10, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="WhenWorldIntent", slot_value="New York")
        handler = lambda_function.WhenWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "available now" in spoken


# ---------------------------------------------------------------------------
# NextWorldIntentHandler
# ---------------------------------------------------------------------------

class TestNextWorldIntentHandler:
    def test_world_changes_tomorrow(self, mock_handler_input, set_lambda_globals, world_list):
        now = datetime(2025, 1, 15, 20, 30, 0)
        midnight = datetime(2025, 1, 16, 0, 0, 0)
        # Day 1 and day 2 are both "paris", so set day=2 where day 3 differs
        set_lambda_globals(
            dayNumber=2, day=2, lastDayOfMonth=31, worldList=world_list,
            nowInHalifax=now, midnightInHalifax=midnight,
        )
        hi = mock_handler_input(intent_name="NextWorldIntent")
        handler = lambda_function.NextWorldIntentHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        # next change is day 3 (1 day away) → hours/minutes until midnight
        assert "hours" in spoken
        assert "minutes" in spoken

    def test_world_changes_in_two_days(self, mock_handler_input, set_lambda_globals, world_list):
        # Day 1 and 2 are both "paris", day 3 is different → from day 1, next change is day 3 (2 days)
        set_lambda_globals(dayNumber=1, day=1, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="NextWorldIntent")
        handler = lambda_function.NextWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "in two days" in spoken

    def test_world_changes_in_n_days(self, mock_handler_input, set_lambda_globals, world_list):
        # Day 3,4 are Yorkshire; day 5 differs → from day 3, change in 2 days
        # Let's use day 21,22 Yorkshire; day 23 London → 2 days
        # For a larger N, we need a longer same-world streak.
        # Days 14,15 London, 16 Richmond → from day 14, change is day 16, 2 days
        # Days 1,2 paris → day 3 Yorkshire, from day 1 that's 2 days.
        # Use a custom worldList for a 3-day gap
        custom = list(world_list)
        custom[5] = custom[3]  # Make days 3,4,5 all the same
        set_lambda_globals(dayNumber=3, day=3, lastDayOfMonth=31, worldList=custom)
        hi = mock_handler_input(intent_name="NextWorldIntent")
        handler = lambda_function.NextWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "3 days from now" in spoken

    def test_no_change_until_end_of_month(self, mock_handler_input, set_lambda_globals):
        # All remaining days are the same world
        wl = ["IndexZero"] + ["Same World"] * 31
        set_lambda_globals(dayNumber=28, day=28, lastDayOfMonth=31, worldList=wl)
        hi = mock_handler_input(intent_name="NextWorldIntent")
        handler = lambda_function.NextWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "don't know next month" in spoken


# ---------------------------------------------------------------------------
# ZwiftTimeIntentHandler
# ---------------------------------------------------------------------------

class TestZwiftTimeIntentHandler:
    def test_returns_day_number(self, mock_handler_input, set_lambda_globals):
        set_lambda_globals(dayNumber=17)
        hi = mock_handler_input(intent_name="ZwiftTimeIntent")
        handler = lambda_function.ZwiftTimeIntentHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "17" in spoken
        assert "Halifax" in spoken


# ---------------------------------------------------------------------------
# HelpIntentHandler
# ---------------------------------------------------------------------------

class TestHelpIntentHandler:
    def test_returns_help_text(self, mock_handler_input):
        hi = mock_handler_input(intent_name="AMAZON.HelpIntent")
        handler = lambda_function.HelpIntentHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "today" in spoken.lower() or "guest worlds" in spoken.lower()


# ---------------------------------------------------------------------------
# CancelOrStopIntentHandler
# ---------------------------------------------------------------------------

class TestCancelOrStopIntentHandler:
    def test_cancel_returns_goodbye(self, mock_handler_input):
        hi = mock_handler_input(intent_name="AMAZON.CancelIntent")
        handler = lambda_function.CancelOrStopIntentHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert spoken == "Goodbye!"

    def test_stop_returns_goodbye(self, mock_handler_input):
        hi = mock_handler_input(intent_name="AMAZON.StopIntent")
        handler = lambda_function.CancelOrStopIntentHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert spoken == "Goodbye!"
