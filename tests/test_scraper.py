"""Tests for guest-world-scraper/getCalendar-writesToStdout.py.

The scraper runs SSM + HTTP calls at module level, so we must patch
dependencies before importing/running the script.
"""

import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest


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
