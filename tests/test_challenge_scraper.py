"""Tests for challenge_scraper_core — pure-function tests for parsing challenge calendar HTML."""

import os
import sys

import pytest

# Make challenge_scraper_core importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "scrapers"))
from challenge_scraper_core import (
    parse_challenge_calendar_html,
    parse_route_detail_page,
    build_challenge_json,
    PHONETIC_OVERRIDES,
)


def _build_challenge_html(day_entries):
    """Build minimal challenge calendar HTML.

    day_entries: list of (day_number, [{"name": str, "xp": int, "category": str,
                 "url": str}, ...]) tuples.
    category is "route" or "climb".
    """
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


# ---------------------------------------------------------------------------
# parse_challenge_calendar_html
# ---------------------------------------------------------------------------

class TestParseChallengeCalendarHtml:
    def test_parses_route_and_climb(self):
        html = _build_challenge_html([
            (1, [
                {"name": "Legends and Lava", "xp": 500, "category": "route",
                 "url": "/route/legends-and-lava/"},
                {"name": "Hardknott Pass", "xp": 250, "category": "climb",
                 "url": "/portal/hardknott-pass/"},
            ]),
        ])
        days = parse_challenge_calendar_html(html)
        assert len(days) == 1
        day_num, challenges = days[0]
        assert day_num == 1
        assert challenges["route"]["name"] == "Legends and Lava"
        assert challenges["route"]["xp"] == 500
        assert "/route/" in challenges["route"]["detail_url"]
        assert challenges["climb"]["name"] == "Hardknott Pass"
        assert challenges["climb"]["xp"] == 250

    def test_multiple_days(self):
        html = _build_challenge_html([
            (1, [
                {"name": "Route A", "xp": 500, "category": "route", "url": "/route/a/"},
                {"name": "Climb A", "xp": 250, "category": "climb", "url": "/portal/a/"},
            ]),
            (8, [
                {"name": "Route B", "xp": 600, "category": "route", "url": "/route/b/"},
                {"name": "Climb B", "xp": 300, "category": "climb", "url": "/portal/b/"},
            ]),
        ])
        days = parse_challenge_calendar_html(html)
        assert len(days) == 2
        assert days[0][0] == 1
        assert days[1][0] == 8
        assert days[1][1]["route"]["name"] == "Route B"

    def test_empty_table(self):
        html = (
            '<html><body>'
            '<table class="spiffy calendar-table bigcal">'
            '<tr><td class="no-date"></td></tr>'
            '</table></body></html>'
        )
        assert parse_challenge_calendar_html(html) == []

    def test_no_table(self):
        assert parse_challenge_calendar_html("<html><body></body></html>") == []

    def test_malformed_xp_skipped(self):
        """Entries without valid XP pattern are skipped."""
        html = (
            '<html><body><table class="spiffy calendar-table bigcal"><tr>'
            '<td class="spiffy-day-1 day-with-date">'
            '<span class="day-number">1</span>'
            '<span class="spiffy-event-group">'
            '<span class="calnk"><span class="calnk-link">'
            '<span class="calnk-box category_367">'
            '<a href="/route/x/"><span class="spiffy-title">No XP Here</span></a>'
            '</span></span></span>'
            '</span></td>'
            '</tr></table></body></html>'
        )
        assert parse_challenge_calendar_html(html) == []

    def test_url_based_classification(self):
        """Falls back to URL pattern when no category class is present."""
        html = (
            '<html><body><table class="spiffy calendar-table bigcal"><tr>'
            '<td class="spiffy-day-1 day-with-date">'
            '<span class="day-number">1</span>'
            '<span class="spiffy-event-group">'
            '<span class="calnk"><span class="calnk-link">'
            '<span class="calnk-box">'
            '<a href="/route/legends/"><span class="spiffy-title">Legends (500XP)</span></a>'
            '</span></span></span>'
            '<span class="calnk"><span class="calnk-link">'
            '<span class="calnk-box">'
            '<a href="/portal/hardknott/"><span class="spiffy-title">Hardknott (250XP)</span></a>'
            '</span></span></span>'
            '</span></td>'
            '</tr></table></body></html>'
        )
        days = parse_challenge_calendar_html(html)
        assert len(days) == 1
        assert days[0][1]["route"]["name"] == "Legends"
        assert days[0][1]["climb"]["name"] == "Hardknott"

    def test_weekend_day_number_class(self):
        """Day cells with 'day-number weekend' class are parsed correctly."""
        html = (
            '<html><body><table class="spiffy calendar-table bigcal"><tr>'
            '<td class="spiffy-day-1 weekend day-with-date">'
            '<span class="day-number weekend">1</span>'
            '<span class="spiffy-event-group">'
            '<span class="calnk"><span class="calnk-link">'
            '<span class="calnk-box category_367">'
            '<a href="/route/x/"><span class="spiffy-title">Weekend Route (500XP)</span></a>'
            '</span></span></span>'
            '</span></td>'
            '</tr></table></body></html>'
        )
        days = parse_challenge_calendar_html(html)
        assert len(days) == 1
        assert days[0][1]["route"]["name"] == "Weekend Route"

    def test_sorts_by_day_number(self):
        html = _build_challenge_html([
            (15, [{"name": "Late", "xp": 500, "category": "route", "url": "/route/late/"}]),
            (1, [{"name": "Early", "xp": 500, "category": "route", "url": "/route/early/"}]),
            (8, [{"name": "Mid", "xp": 500, "category": "route", "url": "/route/mid/"}]),
        ])
        days = parse_challenge_calendar_html(html)
        assert [d[0] for d in days] == [1, 8, 15]

    def test_accepts_bytes(self):
        html = _build_challenge_html([
            (1, [{"name": "Test", "xp": 500, "category": "route", "url": "/route/test/"}]),
        ])
        days = parse_challenge_calendar_html(html.encode("utf-8"))
        assert len(days) == 1


# ---------------------------------------------------------------------------
# parse_route_detail_page
# ---------------------------------------------------------------------------

class TestParseRouteDetailPage:
    def test_parses_distance_and_elevation(self):
        html = '<html><body><p>Distance: 22.5 km (14.0 miles)</p><p>Elevation: 350 m (1,148 ft)</p></body></html>'
        result = parse_route_detail_page(html)
        assert result["distance_km"] == 22.5
        assert result["distance_mi"] == 14.0
        assert result["elevation_m"] == 350.0
        assert result["elevation_ft"] == 1148.0

    def test_distance_only(self):
        html = '<html><body><p>Distance: 10.0 km (6.2 miles)</p></body></html>'
        result = parse_route_detail_page(html)
        assert result["distance_km"] == 10.0
        assert result["distance_mi"] == 6.2
        assert "elevation_m" not in result

    def test_elevation_only(self):
        html = '<html><body><p>Elevation: 500 m (1,640 ft)</p></body></html>'
        result = parse_route_detail_page(html)
        assert "distance_km" not in result
        assert result["elevation_m"] == 500.0
        assert result["elevation_ft"] == 1640.0

    def test_no_data_returns_none(self):
        html = '<html><body><p>No relevant data here.</p></body></html>'
        assert parse_route_detail_page(html) is None

    def test_empty_input_returns_none(self):
        assert parse_route_detail_page("") is None
        assert parse_route_detail_page(None) is None

    def test_elevation_with_apostrophe(self):
        html = "<html><body><p>Elevation: 89 m (292')</p></body></html>"
        result = parse_route_detail_page(html)
        assert result["elevation_m"] == 89.0
        assert result["elevation_ft"] == 292.0


# ---------------------------------------------------------------------------
# build_challenge_json
# ---------------------------------------------------------------------------

class TestBuildChallengeJson:
    def test_basic_structure(self):
        days_by_month = {
            "2026-02": [
                (1, {
                    "route": {"name": "Legends and Lava", "xp": 500, "detail_url": "/route/legends/"},
                    "climb": {"name": "Hardknott Pass", "xp": 250, "detail_url": "/portal/hardknott/"},
                }),
            ],
        }
        result = build_challenge_json(days_by_month)
        assert "2026-02" in result
        assert "1" in result["2026-02"]
        assert result["2026-02"]["1"]["route"]["name"] == "Legends and Lava"
        assert result["2026-02"]["1"]["route"]["xp"] == 500
        assert result["2026-02"]["1"]["climb"]["name"] == "Hardknott Pass"

    def test_merges_route_details(self):
        days_by_month = {
            "2026-02": [
                (1, {
                    "route": {"name": "Test", "xp": 500, "detail_url": "/route/test/"},
                }),
            ],
        }
        route_details = {
            "/route/test/": {"distance_km": 22.5, "distance_mi": 14.0,
                             "elevation_m": 350, "elevation_ft": 1148},
        }
        result = build_challenge_json(days_by_month, route_details)
        entry = result["2026-02"]["1"]["route"]
        assert entry["distance_km"] == 22.5
        assert entry["elevation_ft"] == 1148

    def test_missing_route_detail_omits_distance(self):
        days_by_month = {
            "2026-02": [
                (1, {"route": {"name": "Test", "xp": 500, "detail_url": "/route/test/"}}),
            ],
        }
        result = build_challenge_json(days_by_month, route_details={})
        entry = result["2026-02"]["1"]["route"]
        assert "distance_km" not in entry
        assert "elevation_m" not in entry

    def test_phonetic_override_applied(self):
        days_by_month = {
            "2026-02": [
                (1, {"climb": {"name": "Côte de Pike", "xp": 250, "detail_url": "/portal/cote/"}}),
            ],
        }
        result = build_challenge_json(days_by_month)
        entry = result["2026-02"]["1"]["climb"]
        assert "name_ssml" in entry
        assert "phoneme" in entry["name_ssml"]

    def test_no_phonetic_override_for_plain_name(self):
        days_by_month = {
            "2026-02": [
                (1, {"route": {"name": "Legends and Lava", "xp": 500, "detail_url": "/route/x/"}}),
            ],
        }
        result = build_challenge_json(days_by_month)
        entry = result["2026-02"]["1"]["route"]
        assert "name_ssml" not in entry

    def test_multiple_months(self):
        days_by_month = {
            "2026-02": [
                (1, {"route": {"name": "Feb Route", "xp": 500, "detail_url": None}}),
            ],
            "2026-03": [
                (1, {"route": {"name": "Mar Route", "xp": 600, "detail_url": None}}),
            ],
        }
        result = build_challenge_json(days_by_month)
        assert "2026-02" in result
        assert "2026-03" in result
        assert result["2026-02"]["1"]["route"]["name"] == "Feb Route"
        assert result["2026-03"]["1"]["route"]["name"] == "Mar Route"

    def test_none_detail_url_handled(self):
        days_by_month = {
            "2026-02": [
                (1, {"route": {"name": "Test", "xp": 500, "detail_url": None}}),
            ],
        }
        result = build_challenge_json(days_by_month, route_details={"/route/other/": {}})
        entry = result["2026-02"]["1"]["route"]
        assert entry["name"] == "Test"
        assert "distance_km" not in entry

    def test_detail_returns_none_handled(self):
        """When route_details maps a URL to None, distance/elevation are omitted."""
        days_by_month = {
            "2026-02": [
                (1, {"route": {"name": "Test", "xp": 500, "detail_url": "/route/test/"}}),
            ],
        }
        result = build_challenge_json(days_by_month, route_details={"/route/test/": None})
        entry = result["2026-02"]["1"]["route"]
        assert "distance_km" not in entry
