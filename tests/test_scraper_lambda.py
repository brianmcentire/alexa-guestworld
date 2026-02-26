"""Tests for scrapers/guestworld_scraper_handler.py."""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest

# Add scrapers to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "scrapers"))

from guestworld_scraper_handler import lambda_handler


def _build_calendar_html(world_map):
    """Build minimal schedule HTML for testing."""
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
    rows = "<tr>" + "".join(cells) + "</tr>"
    return (
        '<html><body><table class="spiffy calendar-table bigcal">%s</table></body></html>'
        % rows
    )


class TestScraperLambdaHappyPath:
    def test_scrapes_and_writes_to_s3(self):
        """Lambda writes current files and next-month archive when available."""
        current_world_data = [
            (1, ["Yorkshire", "London"]),
            (2, ["Paris", "France"]),
        ]
        next_world_data = [
            (1, ["Scotland", "New York"]),
        ]
        current_html = _build_calendar_html(current_world_data)
        next_html = _build_calendar_html(next_world_data)

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

        def mock_requests_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "month=" in url:
                resp.content = next_html.encode("utf-8")
            else:
                resp.content = current_html.encode("utf-8")
            return resp

        # Fix utcnow to January 2026 — archive key should be 202601
        fake_now = datetime(2026, 1, 15)

        with (
            patch(
                "guestworld_scraper_handler.boto3.client", side_effect=mock_boto3_client
            ),
            patch(
                "guestworld_scraper_handler.requests.get", side_effect=mock_requests_get
            ),
            patch("guestworld_scraper_handler.datetime") as mock_dt,
        ):
            mock_dt.utcnow.return_value = fake_now
            # Allow timedelta and strftime to work normally
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            result = lambda_handler({}, None)

        assert result["statusCode"] == 200
        assert result["days_scraped"] == 2
        assert result["archive_key"] == "GuestWorlds202601.csv"
        assert result["next_month_available"] is True
        assert result["next_archive_key"] == "GuestWorlds202602.csv"

        # Verify three S3 put_object calls (current primary, current archive, next archive)
        put_calls = mock_s3.put_object.call_args_list
        assert len(put_calls) == 3

        expected_current_csv = "Yorkshire and London,1\nParis and France,2\n"
        expected_next_csv = "Scotland and New York,1\n"
        assert put_calls[0] == call(
            Bucket="guestworldskill",
            Key="GuestWorlds.csv",
            Body=expected_current_csv,
            ACL="public-read",
        )
        assert put_calls[1] == call(
            Bucket="guestworldskill",
            Key="GuestWorlds202601.csv",
            Body=expected_current_csv,
            ACL="public-read",
        )
        assert put_calls[2] == call(
            Bucket="guestworldskill",
            Key="GuestWorlds202602.csv",
            Body=expected_next_csv,
            ACL="public-read",
        )


class TestScraperLambdaNextMonthUnavailable:
    def test_writes_current_month_only_when_next_month_empty(self):
        """If next month has no day data, only current-month files are written."""
        current_world_data = [(1, ["Yorkshire", "London"])]
        current_html = _build_calendar_html(current_world_data)
        empty_next_html = (
            "<html><body>"
            '<table class="spiffy calendar-table bigcal">'
            '<tr><td class="no-date"></td></tr>'
            "</table></body></html>"
        )

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

        def mock_requests_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "month=" in url:
                resp.content = empty_next_html.encode("utf-8")
            else:
                resp.content = current_html.encode("utf-8")
            return resp

        with (
            patch(
                "guestworld_scraper_handler.boto3.client", side_effect=mock_boto3_client
            ),
            patch(
                "guestworld_scraper_handler.requests.get", side_effect=mock_requests_get
            ),
            patch("guestworld_scraper_handler.datetime") as mock_dt,
        ):
            mock_dt.utcnow.return_value = datetime(2026, 1, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            result = lambda_handler({}, None)

        assert result["statusCode"] == 200
        assert result["next_month_available"] is False
        assert result["next_archive_key"] is None
        assert len(mock_s3.put_object.call_args_list) == 2


class TestScraperLambdaNextMonthFetchFailure:
    def test_next_month_fetch_error_still_writes_current_month(self):
        """If next-month fetch fails, current-month files are still written."""
        current_world_data = [(1, ["Yorkshire", "London"])]
        current_html = _build_calendar_html(current_world_data)

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

        def mock_requests_get(url, **kwargs):
            if "month=" in url:
                raise ConnectionError("next-month endpoint unavailable")
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.content = current_html.encode("utf-8")
            return resp

        with (
            patch(
                "guestworld_scraper_handler.boto3.client", side_effect=mock_boto3_client
            ),
            patch(
                "guestworld_scraper_handler.requests.get", side_effect=mock_requests_get
            ),
            patch("guestworld_scraper_handler.datetime") as mock_dt,
        ):
            mock_dt.utcnow.return_value = datetime(2026, 1, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            result = lambda_handler({}, None)

        assert result["statusCode"] == 200
        assert result["archive_key"] == "GuestWorlds202601.csv"
        assert result["next_month_available"] is False
        assert result["next_archive_key"] is None
        assert len(mock_s3.put_object.call_args_list) == 2


class TestScraperLambdaEmptyCalendar:
    def test_raises_value_error(self):
        """Empty calendar raises ValueError."""
        html_content = (
            "<html><body>"
            '<table class="spiffy calendar-table bigcal">'
            '<tr><td class="no-date"></td></tr>'
            "</table></body></html>"
        )

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://example.com/schedule"}
        }

        mock_response = MagicMock()
        mock_response.content = html_content.encode("utf-8")
        mock_response.raise_for_status = MagicMock()

        with (
            patch("guestworld_scraper_handler.boto3.client", return_value=mock_ssm),
            patch(
                "guestworld_scraper_handler.requests.get", return_value=mock_response
            ),
            pytest.raises(ValueError, match="No calendar data found"),
        ):
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

        with (
            patch("guestworld_scraper_handler.boto3.client", return_value=mock_ssm),
            patch(
                "guestworld_scraper_handler.requests.get", return_value=mock_response
            ),
            pytest.raises(HTTPError),
        ):
            lambda_handler({}, None)


class TestScraperLambdaDecemberArchive:
    def test_december_archive_uses_current_month(self):
        """Current archive key for December uses December of current year."""
        world_data = [(1, ["Yorkshire", "London"])]
        html_content = _build_calendar_html(world_data)
        empty_next_html = (
            "<html><body>"
            '<table class="spiffy calendar-table bigcal">'
            '<tr><td class="no-date"></td></tr>'
            "</table></body></html>"
        )

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

        def mock_requests_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "month=" in url:
                resp.content = empty_next_html.encode("utf-8")
            else:
                resp.content = html_content.encode("utf-8")
            return resp

        # Fix utcnow to December 2025 — archive key should be 202512
        fake_now = datetime(2025, 12, 28)

        with (
            patch(
                "guestworld_scraper_handler.boto3.client", side_effect=mock_boto3_client
            ),
            patch(
                "guestworld_scraper_handler.requests.get", side_effect=mock_requests_get
            ),
            patch("guestworld_scraper_handler.datetime") as mock_dt,
        ):
            mock_dt.utcnow.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            result = lambda_handler({}, None)

        assert result["archive_key"] == "GuestWorlds202512.csv"
        assert result["next_month_available"] is False
