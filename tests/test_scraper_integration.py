"""Integration tests for the scraper and SSM pipeline.

These tests hit real AWS SSM Parameter Store and the live schedule website.
They require valid AWS credentials with SSM read access in us-east-1.

Run with:  python3 -m pytest tests/ -v -m integration
"""

import os
import re
import runpy
import sys
from io import StringIO

import boto3
import pytest
import requests

# Make scraper_core importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "guest-world-scraper"))
from scraper_core import parse_calendar_html

pytestmark = pytest.mark.integration

KNOWN_WORLDS = {
    "France",
    "Innsbruck",
    "London",
    "Makuri Islands",
    "New York",
    "Paris",
    "Richmond",
    "Scotland",
    "Yorkshire",
}


@pytest.fixture(scope="module")
def ssm_url():
    """Fetch the scraper URL from SSM Parameter Store (real call)."""
    ssm = boto3.client("ssm", region_name="us-east-1")
    resp = ssm.get_parameter(Name="/guestworld/scraper-url")
    return resp["Parameter"]["Value"]


@pytest.fixture(scope="module")
def calendar_days(ssm_url):
    """Fetch the live schedule page and parse with scraper_core."""
    page = requests.get(ssm_url)
    assert page.status_code == 200
    days = parse_calendar_html(page.content)
    assert len(days) > 0, "Expected calendar data from live page"
    return days


class TestSSMParameter:
    def test_ssm_parameter_is_readable(self):
        """SSM parameter /guestworld/scraper-url exists and looks like a URL."""
        ssm = boto3.client("ssm", region_name="us-east-1")
        resp = ssm.get_parameter(Name="/guestworld/scraper-url")
        value = resp["Parameter"]["Value"]
        assert value.startswith("http"), "Expected URL, got: %s" % value


class TestScheduleWebsite:
    def test_html_structure(self, calendar_days):
        """Schedule page has at least 28 days with world names."""
        assert len(calendar_days) >= 28, "Expected at least 28 days, got %d" % len(calendar_days)

        for day_num, worlds in calendar_days:
            assert isinstance(day_num, int), "Day number should be int"
            assert len(worlds) >= 1, "Day %d should have at least one world" % day_num


class TestWorldNames:
    def test_world_names_are_known(self, calendar_days):
        """All world names in the calendar belong to the known set."""
        unknown = set()
        for _, worlds in calendar_days:
            for w in worlds:
                if w not in KNOWN_WORLDS:
                    unknown.add(w)

        if unknown:
            print("\nUnknown world names found: %s" % unknown)
        assert not unknown, "Unknown world names: %s" % unknown


class TestFullScraperOutput:
    def test_scraper_produces_valid_csv(self):
        """Run the actual scraper and verify CSV output format."""
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured

        try:
            runpy.run_path(
                "guest-world-scraper/getCalendar-writesToStdout.py",
                run_name="__main__",
            )
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        lines = output.strip().split("\n")

        # Should have between 28 and 31 lines (days in a month)
        assert 28 <= len(lines) <= 31, "Expected 28-31 lines, got %d" % len(lines)

        # No blank lines
        assert all(line.strip() for line in lines), "Output contains blank lines"

        # Each line matches "World1 and World2,N" with incrementing day numbers
        for i, line in enumerate(lines, start=1):
            assert re.match(
                r"^.+,\d+$", line
            ), "Line %d doesn't match pattern: %r" % (i, line)
            worlds, day_num = line.rsplit(",", 1)
            assert int(day_num) == i, "Expected day %d, got %s" % (i, day_num)
            # Each world name in the line should be from the known set
            for w in worlds.split(" and "):
                assert w in KNOWN_WORLDS, "Unknown world %r on line %d" % (w, i)
