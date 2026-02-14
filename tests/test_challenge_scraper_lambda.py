"""Tests for scrapers/challenge_scraper_handler.py."""

import json
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest

# Add scrapers to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "scrapers"))

from challenge_scraper_handler import lambda_handler


def _build_challenge_html(day_entries):
    """Build minimal challenge calendar HTML for testing."""
    cells = []
    for day_num, entries in sorted(day_entries, key=lambda x: x[0]):
        events = []
        for entry in entries:
            cat_class = "category_367" if entry["category"] == "route" else "category_370"
            url = entry.get("url", "#")
            events.append(
                '<span class="calnk"><span class="calnk-link">'
                '<span class="calnk-box %s">'
                '<a href="%s"><span class="spiffy-title">%s (%dXP)</span></a>'
                '</span></span></span>'
                % (cat_class, url, entry["name"], entry["xp"])
            )
        cells.append(
            '<td class="spiffy-day-%d day-with-date">'
            '<span class="day-number">%d</span>'
            '<span class="spiffy-event-group">%s</span>'
            '</td>' % (day_num, day_num, "".join(events))
        )
    rows = "<tr>" + "".join(cells) + "</tr>"
    return '<html><body><table class="spiffy calendar-table bigcal">%s</table></body></html>' % rows


def _build_detail_html(distance_km, distance_mi, elevation_m, elevation_ft):
    """Build minimal route detail page HTML."""
    return (
        '<html><body>'
        '<p>Distance: %.1f km (%.1f miles)</p>'
        '<p>Elevation: %d m (%d ft)</p>'
        '</body></html>' % (distance_km, distance_mi, elevation_m, elevation_ft)
    )


class TestChallengeLambdaHappyPath:
    def test_scrapes_two_months_and_detail_pages(self):
        """Lambda scrapes both months, fetches detail pages, writes JSON to S3."""
        current_html = _build_challenge_html([
            (1, [
                {"name": "Legends and Lava", "xp": 500, "category": "route",
                 "url": "/route/legends/"},
                {"name": "Hardknott Pass", "xp": 250, "category": "climb",
                 "url": "/portal/hardknott/"},
            ]),
        ])
        next_html = _build_challenge_html([
            (1, [
                {"name": "Tick Tock", "xp": 600, "category": "route",
                 "url": "/route/tick-tock/"},
                {"name": "Mountain Peak", "xp": 300, "category": "climb",
                 "url": "/portal/mountain/"},
            ]),
        ])
        detail_html = _build_detail_html(22.5, 14.0, 350, 1148)

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://example.com/challenges"}
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
            elif "/route/" in url or "/portal/" in url:
                resp.content = detail_html.encode("utf-8")
            else:
                resp.content = current_html.encode("utf-8")
            return resp

        fake_now = datetime(2026, 2, 10)

        with patch("challenge_scraper_handler.boto3.client", side_effect=mock_boto3_client), \
             patch("challenge_scraper_handler.requests.get", side_effect=mock_requests_get), \
             patch("challenge_scraper_handler.datetime") as mock_dt:
            mock_dt.utcnow.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            result = lambda_handler({}, None)

        assert result["statusCode"] == 200
        assert result["routes_scraped"] == 4  # 2 routes + 2 climbs
        assert "2026-02" in result["months"]
        assert "2026-03" in result["months"]
        assert result["archive_key"] == "WeeklyChallenges202602.json"

        # Verify S3 writes
        put_calls = mock_s3.put_object.call_args_list
        assert len(put_calls) == 2
        assert put_calls[0].kwargs["Key"] == "WeeklyChallenges.json"
        assert put_calls[0].kwargs["ACL"] == "public-read"
        assert put_calls[1].kwargs["Key"] == "WeeklyChallenges202602.json"
        assert put_calls[1].kwargs["ACL"] == "public-read"

        # Verify JSON content has route details
        json_body = json.loads(put_calls[0].kwargs["Body"])
        feb_route = json_body["2026-02"]["1"]["route"]
        assert feb_route["name"] == "Legends and Lava"
        assert feb_route["distance_km"] == 22.5


class TestChallengeLambdaDetailFailure:
    def test_graceful_degradation_on_detail_failure(self):
        """When detail page fetch fails, name+XP are still written."""
        current_html = _build_challenge_html([
            (1, [
                {"name": "Legends", "xp": 500, "category": "route",
                 "url": "/route/legends/"},
            ]),
        ])
        next_html = _build_challenge_html([])  # empty next month

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://example.com/challenges"}
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
            if "/route/" in url or "/portal/" in url:
                raise ConnectionError("Detail page unreachable")
            elif "month=" in url:
                resp.content = next_html.encode("utf-8")
            else:
                resp.content = current_html.encode("utf-8")
            return resp

        fake_now = datetime(2026, 2, 10)

        with patch("challenge_scraper_handler.boto3.client", side_effect=mock_boto3_client), \
             patch("challenge_scraper_handler.requests.get", side_effect=mock_requests_get), \
             patch("challenge_scraper_handler.datetime") as mock_dt:
            mock_dt.utcnow.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            result = lambda_handler({}, None)

        assert result["statusCode"] == 200

        json_body = json.loads(mock_s3.put_object.call_args_list[0].kwargs["Body"])
        route = json_body["2026-02"]["1"]["route"]
        assert route["name"] == "Legends"
        assert route["xp"] == 500
        assert "distance_km" not in route


class TestChallengeLambdaEmptyCalendar:
    def test_raises_value_error(self):
        """Empty calendar for both months raises ValueError."""
        empty_html = (
            '<html><body>'
            '<table class="spiffy calendar-table bigcal">'
            '<tr><td class="no-date"></td></tr>'
            '</table></body></html>'
        ).encode("utf-8")

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://example.com/challenges"}
        }

        def mock_boto3_client(service, **kwargs):
            return mock_ssm

        mock_resp = MagicMock()
        mock_resp.content = empty_html
        mock_resp.raise_for_status = MagicMock()

        with patch("challenge_scraper_handler.boto3.client", side_effect=mock_boto3_client), \
             patch("challenge_scraper_handler.requests.get", return_value=mock_resp), \
             patch("challenge_scraper_handler.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 2, 10)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            with pytest.raises(ValueError, match="No challenge calendar data"):
                lambda_handler({}, None)


class TestChallengeLambdaHTTPError:
    def test_http_error_propagates(self):
        """HTTP errors from the calendar page propagate."""
        from requests.exceptions import HTTPError

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://example.com/challenges"}
        }

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError("500 Server Error")

        with patch("challenge_scraper_handler.boto3.client", return_value=mock_ssm), \
             patch("challenge_scraper_handler.requests.get", return_value=mock_response), \
             pytest.raises(HTTPError):
            lambda_handler({}, None)


class TestChallengeLambdaDecemberRollover:
    def test_december_rolls_to_next_year(self):
        """In December, next month is January of next year."""
        current_html = _build_challenge_html([
            (1, [{"name": "Dec Route", "xp": 500, "category": "route", "url": "/route/dec/"}]),
        ])
        next_html = _build_challenge_html([
            (1, [{"name": "Jan Route", "xp": 600, "category": "route", "url": "/route/jan/"}]),
        ])

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://example.com/challenges"}
        }
        mock_s3 = MagicMock()

        def mock_boto3_client(service, **kwargs):
            if service == "ssm":
                return mock_ssm
            if service == "s3":
                return mock_s3
            raise ValueError("Unexpected service: %s" % service)

        detail_html = _build_detail_html(10.0, 6.2, 100, 328)

        def mock_requests_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "month=jan&yr=2027" in url:
                resp.content = next_html.encode("utf-8")
            elif "/route/" in url:
                resp.content = detail_html.encode("utf-8")
            else:
                resp.content = current_html.encode("utf-8")
            return resp

        fake_now = datetime(2026, 12, 20)

        with patch("challenge_scraper_handler.boto3.client", side_effect=mock_boto3_client), \
             patch("challenge_scraper_handler.requests.get", side_effect=mock_requests_get), \
             patch("challenge_scraper_handler.datetime") as mock_dt:
            mock_dt.utcnow.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            result = lambda_handler({}, None)

        assert "2026-12" in result["months"]
        assert "2027-01" in result["months"]
        assert result["archive_key"] == "WeeklyChallenges202612.json"
