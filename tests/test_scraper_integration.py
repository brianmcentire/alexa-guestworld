"""Integration tests for the scraper and SSM pipeline.

These tests hit real AWS SSM Parameter Store and the live schedule website.
They require valid AWS credentials with SSM read access in us-east-1.

Run with:  python3 -m pytest tests/ -v -m integration
"""

import re
import runpy
import sys
from io import StringIO

import boto3
import pytest
import requests
from lxml import html

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
def calendar_page(ssm_url):
    """Fetch and parse the live schedule page."""
    page = requests.get(ssm_url)
    assert page.status_code == 200
    tree = html.fromstring(page.content)
    table = tree.xpath('//table[contains(@class, "calendar-table")]')
    assert len(table) == 1, "Expected exactly one calendar table"
    return table[0]


class TestSSMParameter:
    def test_ssm_parameter_is_readable(self):
        """SSM parameter /guestworld/scraper-url exists and looks like a URL."""
        ssm = boto3.client("ssm", region_name="us-east-1")
        resp = ssm.get_parameter(Name="/guestworld/scraper-url")
        value = resp["Parameter"]["Value"]
        assert value.startswith("http"), "Expected URL, got: %s" % value


class TestScheduleWebsite:
    def test_html_structure(self, calendar_page):
        """Schedule page has a calendar table with day cells containing world names."""
        cells = calendar_page.xpath('.//td[contains(@class, "day-with-date")]')
        assert len(cells) >= 28, "Expected at least 28 day cells, got %d" % len(cells)

        for cell in cells:
            day_num = cell.xpath('.//span[contains(@class, "day-number")]/text()')
            assert len(day_num) == 1, "Each day cell should have exactly one day-number span"
            assert day_num[0].strip().isdigit(), "Day number should be numeric"

            worlds = cell.xpath('.//span[@class="spiffy-title"]/text()')
            assert len(worlds) >= 1, "Day %s should have at least one world" % day_num[0]


class TestWorldNames:
    def test_world_names_are_known(self, calendar_page):
        """All world names in the calendar belong to the known set."""
        cells = calendar_page.xpath('.//td[contains(@class, "day-with-date")]')
        unknown = set()
        for cell in cells:
            worlds = cell.xpath('.//span[@class="spiffy-title"]/text()')
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
