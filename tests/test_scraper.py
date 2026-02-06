"""Tests for scraper_core and guest-world-scraper/getCalendar-writesToStdout.py.

Pure-function tests for scraper_core come first (fast, no mocking).
CLI script tests use runpy.run_path() with patched boto3/requests.
"""

import os
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

# Make scraper_core importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "guest-world-scraper"))
from scraper_core import parse_calendar_html, format_csv


def _build_calendar_html(world_map):
    """Build minimal HTML containing a calendar table in the zwiftinsider format.

    world_map: list of (day_number, [world_name, ...]) tuples for days with worlds.
    """
    cells = []
    for day_num, worlds in sorted(world_map, key=lambda x: x[0]):
        titles = "".join(
            '<span class="calnk"><span class="calnk-link">'
            '<span class="calnk-box"><a><span class="spiffy-title">%s</span></a>'
            "</span></span></span>" % w
            for w in worlds
        )
        cells.append(
            '<td class="spiffy-day-%d day-with-date">'
            '<span class="day-number">%d</span>'
            '<span class="spiffy-event-group">%s</span>'
            "</td>" % (day_num, day_num, titles)
        )

    # Add an empty cell (no date) to simulate padding days in the calendar grid
    cells.append('<td class="no-date"></td>')

    rows = "<tr>" + "".join(cells) + "</tr>"
    return '<html><body><table class="spiffy calendar-table bigcal">%s</table></body></html>' % rows


# ---------------------------------------------------------------------------
# Pure-function tests for scraper_core
# ---------------------------------------------------------------------------

class TestParseCalendarHtml:
    def test_parses_two_days(self):
        """parse_calendar_html extracts day numbers and world names."""
        html = _build_calendar_html([
            (1, ["Yorkshire", "London"]),
            (2, ["Paris", "France"]),
        ])
        days = parse_calendar_html(html)
        assert len(days) == 2
        assert days[0] == (1, ["Yorkshire", "London"])
        assert days[1] == (2, ["Paris", "France"])

    def test_empty_table_returns_empty(self):
        """Calendar table with no day cells returns empty list."""
        html = (
            '<html><body>'
            '<table class="spiffy calendar-table bigcal">'
            '<tr><td class="no-date"></td></tr>'
            '</table></body></html>'
        )
        assert parse_calendar_html(html) == []

    def test_no_table_returns_empty(self):
        """HTML with no calendar table returns empty list."""
        assert parse_calendar_html("<html><body></body></html>") == []

    def test_weekend_day_number_class(self):
        """Day cells with 'day-number weekend' class are parsed correctly."""
        html = (
            '<html><body>'
            '<table class="spiffy calendar-table bigcal">'
            '<tr>'
            '<td class="spiffy-day-1 weekend day-with-date">'
            '<span class="day-number weekend">1</span>'
            '<span class="spiffy-event-group">'
            '<span class="calnk"><span class="calnk-link">'
            '<span class="calnk-box"><a><span class="spiffy-title">Richmond</span></a>'
            '</span></span></span>'
            '<span class="calnk"><span class="calnk-link">'
            '<span class="calnk-box"><a><span class="spiffy-title">Innsbruck</span></a>'
            '</span></span></span>'
            '</span></td>'
            '</tr></table></body></html>'
        )
        days = parse_calendar_html(html)
        assert len(days) == 1
        assert days[0] == (1, ["Richmond", "Innsbruck"])

    def test_sorts_by_day_number(self):
        """Days are returned sorted even if HTML is out of order."""
        html = _build_calendar_html([
            (3, ["London"]),
            (1, ["Paris"]),
            (2, ["Richmond"]),
        ])
        days = parse_calendar_html(html)
        assert [d[0] for d in days] == [1, 2, 3]

    def test_accepts_bytes(self):
        """parse_calendar_html accepts bytes input."""
        html = _build_calendar_html([(1, ["Yorkshire"])])
        days = parse_calendar_html(html.encode("utf-8"))
        assert len(days) == 1


class TestFormatCsv:
    def test_formats_paired_worlds(self):
        """format_csv joins world names with ' and ' and uses incrementing counter."""
        days = [(1, ["Yorkshire", "London"]), (2, ["Paris", "France"])]
        csv = format_csv(days)
        assert csv == "Yorkshire and London,1\nParis and France,2\n"

    def test_single_world(self):
        """format_csv works with single-world days."""
        days = [(5, ["Richmond"])]
        csv = format_csv(days)
        assert csv == "Richmond,1\n"

    def test_empty_days(self):
        """format_csv returns empty string for empty input."""
        assert format_csv([]) == ""


# ---------------------------------------------------------------------------
# CLI script tests (end-to-end via runpy)
# ---------------------------------------------------------------------------

class TestScraperValidHTML:
    def test_outputs_csv_lines(self):
        """Valid calendar data produces correct CSV output."""
        world_data = [
            (1, ["Yorkshire", "London"]),
            (2, ["Paris", "France"]),
        ]
        html_content = _build_calendar_html(world_data)

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://example.com/schedule"}
        }

        mock_response = MagicMock()
        mock_response.content = html_content.encode("utf-8")

        with patch("boto3.client", return_value=mock_ssm), \
             patch("requests.get", return_value=mock_response):
            captured = StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured

            import runpy
            runpy.run_path(
                "guest-world-scraper/getCalendar-writesToStdout.py",
                run_name="__main__",
            )

            sys.stdout = old_stdout

        lines = captured.getvalue().strip().split("\n")
        assert len(lines) == 2
        assert lines[0] == "Yorkshire and London,1"
        assert lines[1] == "Paris and France,2"


class TestScraperSSMFailure:
    def test_ssm_client_error_raises(self):
        """SSM failure propagates as an exception."""
        from botocore.exceptions import ClientError

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "not found"}},
            "GetParameter",
        )

        with patch("boto3.client", return_value=mock_ssm), \
             pytest.raises(ClientError):
            import runpy
            runpy.run_path(
                "guest-world-scraper/getCalendar-writesToStdout.py",
                run_name="__main__",
            )


class TestScraperHTTPFailure:
    def test_connection_error_raises(self):
        """HTTP failure propagates as an exception."""
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://example.com/schedule"}
        }

        with patch("boto3.client", return_value=mock_ssm), \
             patch("requests.get", side_effect=ConnectionError("refused")), \
             pytest.raises(ConnectionError):
            import runpy
            runpy.run_path(
                "guest-world-scraper/getCalendar-writesToStdout.py",
                run_name="__main__",
            )


class TestScraperEmptyCalendar:
    def test_no_output_for_empty_table(self):
        """Calendar table with no day-with-date cells produces no output."""
        html_content = (
            '<html><body>'
            '<table class="spiffy calendar-table bigcal">'
            '<tr><td class="no-date"></td></tr>'
            '</table></body></html>'
        )

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://example.com/schedule"}
        }

        mock_response = MagicMock()
        mock_response.content = html_content.encode("utf-8")

        with patch("boto3.client", return_value=mock_ssm), \
             patch("requests.get", return_value=mock_response):
            captured = StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured

            import runpy
            runpy.run_path(
                "guest-world-scraper/getCalendar-writesToStdout.py",
                run_name="__main__",
            )

            sys.stdout = old_stdout

        output = captured.getvalue().strip()
        assert output == ""


class TestScraperWeekendDayNumber:
    def test_weekend_day_number_class(self):
        """Day cells with 'day-number weekend' class are parsed correctly."""
        html_content = (
            '<html><body>'
            '<table class="spiffy calendar-table bigcal">'
            '<tr>'
            '<td class="spiffy-day-1 weekend day-with-date">'
            '<span class="day-number weekend">1</span>'
            '<span class="spiffy-event-group">'
            '<span class="calnk"><span class="calnk-link">'
            '<span class="calnk-box"><a><span class="spiffy-title">Richmond</span></a>'
            '</span></span></span>'
            '<span class="calnk"><span class="calnk-link">'
            '<span class="calnk-box"><a><span class="spiffy-title">Innsbruck</span></a>'
            '</span></span></span>'
            '</span></td>'
            '</tr></table></body></html>'
        )

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://example.com/schedule"}
        }

        mock_response = MagicMock()
        mock_response.content = html_content.encode("utf-8")

        with patch("boto3.client", return_value=mock_ssm), \
             patch("requests.get", return_value=mock_response):
            captured = StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured

            import runpy
            runpy.run_path(
                "guest-world-scraper/getCalendar-writesToStdout.py",
                run_name="__main__",
            )

            sys.stdout = old_stdout

        lines = captured.getvalue().strip().split("\n")
        assert len(lines) == 1
        assert lines[0] == "Richmond and Innsbruck,1"
