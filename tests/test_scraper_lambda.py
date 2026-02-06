"""Tests for scraper-lambda/scraper_handler.py."""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest

# Add scraper-lambda and guest-world-scraper to path
_REPO = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.insert(0, os.path.join(_REPO, "scraper-lambda"))
sys.path.insert(0, os.path.join(_REPO, "guest-world-scraper"))

from scraper_handler import lambda_handler


def _build_calendar_html(world_map):
    """Build minimal schedule HTML for testing."""
    cells = []
    for day_num, worlds in sorted(world_map, key=lambda x: x[0]):
        titles = "".join(
            '<span class="calnk"><span class="calnk-link">'
            '<span class="calnk-box"><a><span class="spiffy-title">%s</span></a>'
            '</span></span></span>' % w
            for w in worlds
        )
        cells.append(
            '<td class="spiffy-day-%d day-with-date">'
            '<span class="day-number">%d</span>'
            '<span class="spiffy-event-group">%s</span>'
            '</td>' % (day_num, day_num, titles)
        )
    rows = "<tr>" + "".join(cells) + "</tr>"
    return '<html><body><table class="spiffy calendar-table bigcal">%s</table></body></html>' % rows


class TestScraperLambdaHappyPath:
    def test_scrapes_and_writes_to_s3(self):
        """Lambda reads SSM, fetches HTML, parses, and writes two S3 objects."""
        world_data = [
            (1, ["Yorkshire", "London"]),
            (2, ["Paris", "France"]),
        ]
        html_content = _build_calendar_html(world_data)

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://example.com/schedule"}
        }

        mock_s3 = MagicMock()

        def mock_boto3_client(service, **kwargs):
            if service == "ssm":
                return mock_ssm
            if service == "s3":
                return mock_s3
            raise ValueError("Unexpected service: %s" % service)

        mock_response = MagicMock()
        mock_response.content = html_content.encode("utf-8")
        mock_response.raise_for_status = MagicMock()

        # Fix utcnow to January 2026 — archive key should be 202602
        fake_now = datetime(2026, 1, 15)

        with patch("scraper_handler.boto3.client", side_effect=mock_boto3_client), \
             patch("scraper_handler.requests.get", return_value=mock_response), \
             patch("scraper_handler.datetime") as mock_dt:
            mock_dt.utcnow.return_value = fake_now
            # Allow timedelta and strftime to work normally
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            result = lambda_handler({}, None)

        assert result["statusCode"] == 200
        assert result["days_scraped"] == 2
        assert result["archive_key"] == "GuestWorlds202602.csv"

        # Verify two S3 put_object calls
        put_calls = mock_s3.put_object.call_args_list
        assert len(put_calls) == 2

        expected_csv = "Yorkshire and London,1\nParis and France,2\n"
        assert put_calls[0] == call(
            Bucket="guestworldskill", Key="GuestWorlds.csv", Body=expected_csv
        )
        assert put_calls[1] == call(
            Bucket="guestworldskill", Key="GuestWorlds202602.csv", Body=expected_csv
        )

        mock_response.raise_for_status.assert_called_once()


class TestScraperLambdaEmptyCalendar:
    def test_raises_value_error(self):
        """Empty calendar raises ValueError."""
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
        mock_response.raise_for_status = MagicMock()

        with patch("scraper_handler.boto3.client", return_value=mock_ssm), \
             patch("scraper_handler.requests.get", return_value=mock_response), \
             pytest.raises(ValueError, match="No calendar data found"):
            lambda_handler({}, None)


class TestScraperLambdaHTTPError:
    def test_http_error_propagates(self):
        """HTTP errors from requests propagate."""
        from requests.exceptions import HTTPError

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://example.com/schedule"}
        }

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError("500 Server Error")

        with patch("scraper_handler.boto3.client", return_value=mock_ssm), \
             patch("scraper_handler.requests.get", return_value=mock_response), \
             pytest.raises(HTTPError):
            lambda_handler({}, None)


class TestScraperLambdaDecemberArchive:
    def test_december_rolls_to_next_year(self):
        """Archive key for December scrape uses next year's January."""
        world_data = [(1, ["Yorkshire", "London"])]
        html_content = _build_calendar_html(world_data)

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://example.com/schedule"}
        }

        mock_s3 = MagicMock()

        def mock_boto3_client(service, **kwargs):
            if service == "ssm":
                return mock_ssm
            if service == "s3":
                return mock_s3
            raise ValueError("Unexpected service: %s" % service)

        mock_response = MagicMock()
        mock_response.content = html_content.encode("utf-8")
        mock_response.raise_for_status = MagicMock()

        # Fix utcnow to December 2025 — archive key should be 202601
        fake_now = datetime(2025, 12, 28)

        with patch("scraper_handler.boto3.client", side_effect=mock_boto3_client), \
             patch("scraper_handler.requests.get", return_value=mock_response), \
             patch("scraper_handler.datetime") as mock_dt:
            mock_dt.utcnow.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            result = lambda_handler({}, None)

        assert result["archive_key"] == "GuestWorlds202601.csv"
