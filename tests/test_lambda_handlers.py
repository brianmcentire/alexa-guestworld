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
        set_lambda_globals(day=5, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="TodaysWorldIntent")
        handler = lambda_function.TodaysWorldIntentHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert world_list[5] in spoken
        assert "Todays Guest Worlds" in spoken

    def test_data_unavailable(self, mock_handler_input, set_lambda_globals):
        set_lambda_globals(day=5, lastDayOfMonth=31)
        lambda_function.worldList = None
        hi = mock_handler_input(intent_name="TodaysWorldIntent")
        handler = lambda_function.TodaysWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "temporarily unavailable" in spoken


# ---------------------------------------------------------------------------
# TomorrowsWorldIntentHandler
# ---------------------------------------------------------------------------

class TestTomorrowsWorldIntentHandler:
    def test_mid_month(self, mock_handler_input, set_lambda_globals, world_list):
        set_lambda_globals(day=10, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="TomorrowsWorldIntent")
        handler = lambda_function.TomorrowsWorldIntentHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert world_list[11] in spoken
        assert "Tomorrow" in spoken

    def test_end_of_month(self, mock_handler_input, set_lambda_globals, world_list):
        set_lambda_globals(day=31, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="TomorrowsWorldIntent")
        handler = lambda_function.TomorrowsWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "don't know next month" in spoken
        assert world_list[31] in spoken

    def test_day_before_last(self, mock_handler_input, set_lambda_globals, world_list):
        # Day 30 of a 31-day month: day < last_day (30 < 31) so tomorrow's worlds are returned
        set_lambda_globals(day=30, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="TomorrowsWorldIntent")
        handler = lambda_function.TomorrowsWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "Tomorrow" in spoken
        assert world_list[31] in spoken


# ---------------------------------------------------------------------------
# WhenWorldIntentHandler
# ---------------------------------------------------------------------------

class TestWhenWorldIntentHandler:
    def test_watopia_always_available(self, mock_handler_input, set_lambda_globals, world_list):
        set_lambda_globals(day=5, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="WhenWorldIntent", slot_value="Watopia")
        handler = lambda_function.WhenWorldIntentHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "Watopia" in spoken
        assert "every day" in spoken

    def test_world_available_today(self, mock_handler_input, set_lambda_globals, world_list):
        # Day 3 has "Yorkshire and Innsbruck"
        set_lambda_globals(day=3, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="WhenWorldIntent", slot_value="Yorkshire")
        handler = lambda_function.WhenWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "available now" in spoken

    def test_world_available_tomorrow(self, mock_handler_input, set_lambda_globals, world_list):
        # Day 2 has "paris", day 3 has "Yorkshire and Innsbruck"
        set_lambda_globals(day=2, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="WhenWorldIntent", slot_value="Yorkshire")
        handler = lambda_function.WhenWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "available tomorrow" in spoken

    def test_world_available_in_n_days(self, mock_handler_input, set_lambda_globals, world_list):
        # Day 1 = paris, Yorkshire first appears on day 3 → 2 days away
        set_lambda_globals(day=1, lastDayOfMonth=31, worldList=world_list,
                           nowInHalifax=datetime(2025, 1, 1, 12, 0, 0))
        hi = mock_handler_input(intent_name="WhenWorldIntent", slot_value="Yorkshire")
        handler = lambda_function.WhenWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "in 2 days" in spoken
        assert "January the 3rd" in spoken

    def test_world_not_found_this_month(self, mock_handler_input, set_lambda_globals, world_list):
        # Ask for London starting from day 28 — London doesn't appear after day 24
        set_lambda_globals(day=28, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="WhenWorldIntent", slot_value="London")
        handler = lambda_function.WhenWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "next month" in spoken

    def test_case_insensitive_match(self, mock_handler_input, set_lambda_globals, world_list):
        # "new york" should match "New York and Richmond" on day 10
        set_lambda_globals(day=10, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="WhenWorldIntent", slot_value="New York")
        handler = lambda_function.WhenWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "available now" in spoken

    def test_slot_resolution_failure(self, mock_handler_input, set_lambda_globals, world_list):
        set_lambda_globals(day=5, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="WhenWorldIntent", slot_resolution_fails=True)
        handler = lambda_function.WhenWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "didn't catch" in spoken


# ---------------------------------------------------------------------------
# NextWorldIntentHandler
# ---------------------------------------------------------------------------

class TestNextWorldIntentHandler:
    def test_world_changes_tomorrow(self, mock_handler_input, set_lambda_globals, world_list):
        now = datetime(2025, 1, 15, 20, 30, 0)
        midnight = datetime(2025, 1, 16, 0, 0, 0)
        # Day 1 and day 2 are both "paris", so set day=2 where day 3 differs
        set_lambda_globals(
            day=2, lastDayOfMonth=31, worldList=world_list,
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
        set_lambda_globals(day=1, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="NextWorldIntent")
        handler = lambda_function.NextWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "in two days" in spoken

    def test_world_changes_in_n_days(self, mock_handler_input, set_lambda_globals, world_list):
        # Use a custom worldList for a 3-day gap
        custom = list(world_list)
        custom[5] = custom[3]  # Make days 3,4,5 all the same
        set_lambda_globals(day=3, lastDayOfMonth=31, worldList=custom)
        hi = mock_handler_input(intent_name="NextWorldIntent")
        handler = lambda_function.NextWorldIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "3 days from now" in spoken

    def test_no_change_until_end_of_month(self, mock_handler_input, set_lambda_globals):
        # All remaining days are the same world
        wl = ["IndexZero"] + ["Same World"] * 31
        set_lambda_globals(day=28, lastDayOfMonth=31, worldList=wl)
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
        set_lambda_globals(day=17)
        hi = mock_handler_input(intent_name="ZwiftTimeIntent")
        handler = lambda_function.ZwiftTimeIntentHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "17" in spoken
        assert "Halifax" in spoken

    def test_uses_fresh_time(self, mock_handler_input, set_lambda_globals):
        # First call with day=10, second with day=25 — verify it picks up the change
        set_lambda_globals(day=10)
        hi = mock_handler_input(intent_name="ZwiftTimeIntent")
        handler = lambda_function.ZwiftTimeIntentHandler()
        handler.handle(hi)
        spoken = hi.response_builder.speak.call_args[0][0]
        assert "10" in spoken

        set_lambda_globals(day=25)
        hi2 = mock_handler_input(intent_name="ZwiftTimeIntent")
        handler.handle(hi2)
        spoken2 = hi2.response_builder.speak.call_args[0][0]
        assert "25" in spoken2


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


# ---------------------------------------------------------------------------
# _ordinal_date_string
# ---------------------------------------------------------------------------

class TestOrdinalDateString:
    def test_1st(self):
        assert lambda_function._ordinal_date_string(datetime(2025, 1, 1)) == "January the 1st"

    def test_2nd(self):
        assert lambda_function._ordinal_date_string(datetime(2025, 1, 2)) == "January the 2nd"

    def test_3rd(self):
        assert lambda_function._ordinal_date_string(datetime(2025, 1, 3)) == "January the 3rd"

    def test_11th(self):
        assert lambda_function._ordinal_date_string(datetime(2025, 1, 11)) == "January the 11th"

    def test_12th(self):
        assert lambda_function._ordinal_date_string(datetime(2025, 1, 12)) == "January the 12th"

    def test_13th(self):
        assert lambda_function._ordinal_date_string(datetime(2025, 1, 13)) == "January the 13th"

    def test_21st(self):
        assert lambda_function._ordinal_date_string(datetime(2025, 1, 21)) == "January the 21st"

    def test_30th(self):
        assert lambda_function._ordinal_date_string(datetime(2025, 1, 30)) == "January the 30th"


# ---------------------------------------------------------------------------
# _parse_amazon_date
# ---------------------------------------------------------------------------

class TestParseAmazonDate:
    def test_same_month_date(self):
        now = datetime(2025, 1, 10)
        result = lambda_function._parse_amazon_date("2025-01-15", now)
        assert result == [(15, datetime(2025, 1, 15))]

    def test_different_month_date(self):
        now = datetime(2025, 1, 10)
        result = lambda_function._parse_amazon_date("2025-02-15", now)
        assert result == []

    def test_weekend_both_in_month(self):
        # Week 2 of 2025: Sat=Jan 11, Sun=Jan 12
        now = datetime(2025, 1, 10)
        result = lambda_function._parse_amazon_date("2025-W02-WE", now)
        assert len(result) == 2
        assert result[0][0] == 11
        assert result[1][0] == 12

    def test_weekend_spanning_month_boundary(self):
        # Week 5 of 2025: Sat=Feb 1, Sun=Feb 2 — January has 31 days
        now = datetime(2025, 1, 30)
        result = lambda_function._parse_amazon_date("2025-W05-WE", now)
        assert result == []  # Both days are in February, not January

    def test_empty_string(self):
        now = datetime(2025, 1, 10)
        assert lambda_function._parse_amazon_date("", now) == []

    def test_none(self):
        now = datetime(2025, 1, 10)
        assert lambda_function._parse_amazon_date(None, now) == []

    def test_unparseable(self):
        now = datetime(2025, 1, 10)
        assert lambda_function._parse_amazon_date("not-a-date", now) == []

    def test_recurring_day_of_month(self):
        now = datetime(2025, 1, 10)
        result = lambda_function._parse_amazon_date("XXXX-XX-15", now)
        assert result == [(15, datetime(2025, 1, 15))]

    def test_recurring_day_out_of_range(self):
        # February has 28 days, so day 31 is out of range
        now = datetime(2025, 2, 10)
        assert lambda_function._parse_amazon_date("XXXX-XX-31", now) == []

    def test_weekend_single_digit_week(self):
        # W7 (no leading zero) should parse the same as W07
        now = datetime(2025, 2, 10)
        result = lambda_function._parse_amazon_date("2025-W7-WE", now)
        assert len(result) == 2
        assert result[0][0] == 15  # Saturday Feb 15
        assert result[1][0] == 16  # Sunday Feb 16


# ---------------------------------------------------------------------------
# WorldOnDateIntentHandler
# ---------------------------------------------------------------------------

class TestWorldOnDateIntentHandler:
    def test_future_date(self, mock_handler_input, set_lambda_globals, world_list):
        # Day 10, ask about the 15th — "London and Yorkshire"
        set_lambda_globals(day=10, lastDayOfMonth=31, worldList=world_list,
                           nowInHalifax=datetime(2025, 1, 10, 12, 0, 0))
        hi = mock_handler_input(intent_name="WorldOnDateIntent",
                                date_slot_value="2025-01-15")
        handler = lambda_function.WorldOnDateIntentHandler()

        assert handler.can_handle(hi)
        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "January the 15th" in spoken
        assert "London and Yorkshire" in spoken

    def test_today(self, mock_handler_input, set_lambda_globals, world_list):
        # Ask about today (day 5) — "London and Yorkshire"
        set_lambda_globals(day=5, lastDayOfMonth=31, worldList=world_list,
                           nowInHalifax=datetime(2025, 1, 5, 12, 0, 0))
        hi = mock_handler_input(intent_name="WorldOnDateIntent",
                                date_slot_value="2025-01-05")
        handler = lambda_function.WorldOnDateIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "January the 5th" in spoken
        assert "London and Yorkshire" in spoken

    def test_past_date(self, mock_handler_input, set_lambda_globals, world_list):
        # Day 10, ask about the 3rd — past
        set_lambda_globals(day=10, lastDayOfMonth=31, worldList=world_list,
                           nowInHalifax=datetime(2025, 1, 10, 12, 0, 0))
        hi = mock_handler_input(intent_name="WorldOnDateIntent",
                                date_slot_value="2025-01-03")
        handler = lambda_function.WorldOnDateIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "already passed" in spoken
        assert "available today" in spoken

    def test_weekend_same_worlds(self, mock_handler_input, set_lambda_globals, world_list):
        # Week 4 of 2025: Sat=Jan 25, Sun=Jan 26 — both "paris" (day 26) and
        # "Richmond and London" (day 25) — actually check: day 25="Richmond and London",
        # day 26="paris" — different, so use a weekend with same worlds.
        # Days 7-8: "Richmond and London" and "Makuri Islands and New York" — different.
        # Days 1-2: "paris" and "paris" — same! But need a weekend.
        # Let's use a custom world list for clarity.
        custom = list(world_list)
        custom[11] = custom[12]  # Make Sat/Sun of week 2 the same
        set_lambda_globals(day=8, lastDayOfMonth=31, worldList=custom,
                           nowInHalifax=datetime(2025, 1, 8, 12, 0, 0))
        hi = mock_handler_input(intent_name="WorldOnDateIntent",
                                date_slot_value="2025-W02-WE")
        handler = lambda_function.WorldOnDateIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "Saturday and Sunday" in spoken
        assert custom[11] in spoken

    def test_weekend_different_worlds(self, mock_handler_input, set_lambda_globals, world_list):
        # Week 1 of 2025: Sat=Jan 4, Sun=Jan 5
        # Day 4 = "Yorkshire and Innsbruck", day 5 = "London and Yorkshire" → different
        set_lambda_globals(day=1, lastDayOfMonth=31, worldList=world_list,
                           nowInHalifax=datetime(2025, 1, 1, 12, 0, 0))
        hi = mock_handler_input(intent_name="WorldOnDateIntent",
                                date_slot_value="2025-W01-WE")
        handler = lambda_function.WorldOnDateIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "Saturday" in spoken
        assert "Sunday" in spoken
        assert "Yorkshire and Innsbruck" in spoken
        assert "London and Yorkshire" in spoken

    def test_weekend_on_sunday(self, mock_handler_input, set_lambda_globals, world_list):
        # Today is Sunday Jan 5, ask "this weekend" → Sat Jan 4 is past, only Sun Jan 5
        set_lambda_globals(day=5, lastDayOfMonth=31, worldList=world_list,
                           nowInHalifax=datetime(2025, 1, 5, 12, 0, 0))
        hi = mock_handler_input(intent_name="WorldOnDateIntent",
                                date_slot_value="2025-W01-WE")
        handler = lambda_function.WorldOnDateIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        # Only Sunday should be mentioned (Saturday is past)
        assert "January the 5th" in spoken
        assert "London and Yorkshire" in spoken

    def test_next_month_date(self, mock_handler_input, set_lambda_globals, world_list):
        set_lambda_globals(day=10, lastDayOfMonth=31, worldList=world_list,
                           nowInHalifax=datetime(2025, 1, 10, 12, 0, 0))
        hi = mock_handler_input(intent_name="WorldOnDateIntent",
                                date_slot_value="2025-02-15")
        handler = lambda_function.WorldOnDateIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "don't have the schedule" in spoken

    def test_missing_slot(self, mock_handler_input, set_lambda_globals, world_list):
        set_lambda_globals(day=10, lastDayOfMonth=31, worldList=world_list)
        hi = mock_handler_input(intent_name="WorldOnDateIntent")
        handler = lambda_function.WorldOnDateIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "didn't catch" in spoken

    def test_recurring_day_of_month(self, mock_handler_input, set_lambda_globals, world_list):
        # "the 27th" → XXXX-XX-27 → day 27 = "paris"
        set_lambda_globals(day=10, lastDayOfMonth=31, worldList=world_list,
                           nowInHalifax=datetime(2025, 1, 10, 12, 0, 0))
        hi = mock_handler_input(intent_name="WorldOnDateIntent",
                                date_slot_value="XXXX-XX-27")
        handler = lambda_function.WorldOnDateIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "January the 27th" in spoken
        assert "paris" in spoken

    def test_weekend_single_digit_week(self, mock_handler_input, set_lambda_globals, world_list):
        # "next weekend" → 2025-W2-WE (no leading zero) → Sat Jan 11, Sun Jan 12
        set_lambda_globals(day=8, lastDayOfMonth=31, worldList=world_list,
                           nowInHalifax=datetime(2025, 1, 8, 12, 0, 0))
        hi = mock_handler_input(intent_name="WorldOnDateIntent",
                                date_slot_value="2025-W2-WE")
        handler = lambda_function.WorldOnDateIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "Saturday" in spoken
        assert "Sunday" in spoken

    def test_data_unavailable(self, mock_handler_input, set_lambda_globals):
        set_lambda_globals(day=10, lastDayOfMonth=31)
        lambda_function.worldList = None
        hi = mock_handler_input(intent_name="WorldOnDateIntent",
                                date_slot_value="2025-01-15")
        handler = lambda_function.WorldOnDateIntentHandler()

        handler.handle(hi)

        spoken = hi.response_builder.speak.call_args[0][0]
        assert "temporarily unavailable" in spoken
