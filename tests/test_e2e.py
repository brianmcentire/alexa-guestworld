"""End-to-end smoke tests using ASK CLI dialog replay.

Sends real utterances through Alexa's NLU and verifies the skill responses
contain expected phrases, catching intent misrouting across locales.

Run:    pytest tests/test_e2e.py -v
        pytest tests/test_e2e.py -v -k "en_AU"   (single locale)

Requires: ASK CLI installed and configured with valid credentials.
Excluded by default via the 'e2e' marker in pyproject.toml.
"""

import json
import os
import shutil
import subprocess
import tempfile

import pytest

SKILL_ID = "amzn1.ask.skill.44ca3fd7-539b-4349-9c93-275ba6fd3184"
LOCALES = ["en-US", "en-AU", "en-CA", "en-GB"]

pytestmark = pytest.mark.e2e


def _ask_cli_available():
    return shutil.which("ask") is not None


def run_dialog(locale, utterances):
    """Run ask dialog --replay and return list of Alexa response strings."""
    replay = {
        "skillId": SKILL_ID,
        "locale": locale,
        "type": "text",
        "userInput": utterances,
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(replay, f)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["ask", "dialog", "--replay", tmp_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        os.unlink(tmp_path)

    if result.returncode != 0:
        pytest.fail(f"ask dialog failed (rc={result.returncode}): {result.stderr}")

    # Check for errors in output (e.g. locale not built, simulation API failures)
    if "[Error]" in result.stdout or "RetriableServiceError" in result.stdout:
        pytest.fail(
            f"ask dialog returned an error for {locale}. "
            f"Is the interaction model built for this locale?\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout[:500]}"
        )

    # Parse Alexa responses from output.
    # Format: "  Alexa >  response text here"
    # Responses may span multiple lines.
    responses = []
    current_response = None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if "Alexa >" in stripped:
            if current_response is not None:
                responses.append(current_response)
            current_response = stripped.split("Alexa >", 1)[1].strip()
        elif "User  >" in stripped:
            if current_response is not None:
                responses.append(current_response)
                current_response = None
        elif current_response is not None and stripped:
            current_response += " " + stripped
    if current_response is not None:
        responses.append(current_response)

    return responses


skip_no_ask = pytest.mark.skipif(
    not _ask_cli_available(), reason="ASK CLI not installed"
)


@pytest.fixture(params=LOCALES, ids=LOCALES)
def locale(request):
    return request.param


def _assert_no_errors(response):
    """Assert the response is not a Lambda error or data-unavailable message."""
    rl = response.lower()
    assert "sorry" not in rl, f"Got error: {response}"
    assert "trouble" not in rl, f"Got error: {response}"
    assert "didn't catch" not in rl, f"Got misroute: {response}"


# ---------------------------------------------------------------------------
# WorldOnDateIntent — the original cross-locale bug
# ---------------------------------------------------------------------------


@skip_no_ask
class TestWorldOnDateIntent:
    """Date queries must route to WorldOnDateIntent, not WhenWorldIntent."""

    def test_ride_on_day_of_week(self, locale):
        """'where can i ride on sunday' — the original en-AU failure."""
        responses = run_dialog(locale, [
            "ask which world where can i ride on sunday"
        ])
        assert len(responses) >= 1
        r = responses[0].lower()
        assert "guest worlds will be" in r
        assert "didn't catch which world" not in r

    def test_ride_day_of_week_without_on(self, locale):
        """'where can i ride sunday' (no preposition) should also work."""
        responses = run_dialog(locale, [
            "ask which world where can i ride sunday"
        ])
        assert len(responses) >= 1
        r = responses[0].lower()
        assert "guest worlds will be" in r
        assert "didn't catch which world" not in r

    def test_what_available_on_saturday(self, locale):
        responses = run_dialog(locale, [
            "ask which world what is available on saturday"
        ])
        assert len(responses) >= 1
        r = responses[0].lower()
        assert "guest worlds will be" in r or "saturday" in r
        assert "didn't catch" not in r

    def test_weekend_query(self, locale):
        responses = run_dialog(locale, [
            "ask which world what can i ride this weekend"
        ])
        assert len(responses) >= 1
        r = responses[0].lower()
        assert "guest worlds will be" in r or "saturday" in r
        assert "didn't catch which world" not in r


# ---------------------------------------------------------------------------
# TodaysWorldIntent
# ---------------------------------------------------------------------------


@skip_no_ask
class TestTodaysWorldIntent:
    """Today-oriented queries must route to TodaysWorldIntent."""

    def test_ride_today(self, locale):
        responses = run_dialog(locale, [
            "ask which world where can i ride today"
        ])
        assert len(responses) >= 1
        assert "todays guest worlds are" in responses[0].lower()

    def test_bare_what_can_i_ride(self, locale):
        """'what can i ride' with no time word should default to today."""
        responses = run_dialog(locale, [
            "ask which world what can i ride"
        ])
        assert len(responses) >= 1
        assert "todays guest worlds are" in responses[0].lower()

    def test_what_can_i_ride_now(self, locale):
        responses = run_dialog(locale, [
            "ask which world what can i ride now"
        ])
        assert len(responses) >= 1
        assert "todays guest worlds are" in responses[0].lower()

    def test_what_is_available(self, locale):
        responses = run_dialog(locale, [
            "ask which world what is available"
        ])
        assert len(responses) >= 1
        assert "todays guest worlds are" in responses[0].lower()


# ---------------------------------------------------------------------------
# TomorrowsWorldIntent
# ---------------------------------------------------------------------------


@skip_no_ask
class TestTomorrowsWorldIntent:

    def test_ride_tomorrow(self, locale):
        responses = run_dialog(locale, [
            "ask which world where can i ride tomorrow"
        ])
        assert len(responses) >= 1
        r = responses[0].lower()
        assert "tomorrow" in r or "don't know next month" in r

    def test_what_about_tomorrow(self, locale):
        responses = run_dialog(locale, [
            "ask which world what about tomorrow"
        ])
        assert len(responses) >= 1
        r = responses[0].lower()
        assert "tomorrow" in r or "don't know next month" in r


# ---------------------------------------------------------------------------
# WhenWorldIntent
# ---------------------------------------------------------------------------


@skip_no_ask
class TestWhenWorldIntent:

    def test_when_is_london(self, locale):
        responses = run_dialog(locale, [
            "ask which world when is london"
        ])
        assert len(responses) >= 1
        r = responses[0].lower()
        assert "london" in r
        assert "didn't catch which world" not in r

    def test_watopia_always_available(self, locale):
        responses = run_dialog(locale, [
            "ask which world when is watopia"
        ])
        assert len(responses) >= 1
        assert "every day" in responses[0].lower()

    def test_when_is_yorkshire(self, locale):
        responses = run_dialog(locale, [
            "ask which world when is yorkshire"
        ])
        assert len(responses) >= 1
        r = responses[0].lower()
        assert "yorkshire" in r
        assert "didn't catch which world" not in r


# ---------------------------------------------------------------------------
# NextWorldIntent
# ---------------------------------------------------------------------------


@skip_no_ask
class TestNextWorldIntent:

    def test_what_is_next(self, locale):
        responses = run_dialog(locale, [
            "ask which world what is next"
        ])
        assert len(responses) >= 1
        r = responses[0].lower()
        assert any(phrase in r for phrase in [
            "next worlds will be", "available", "active through",
            "hour", "minute", "days from now",
        ])


# ---------------------------------------------------------------------------
# Multi-turn / AfterThatIntent
# ---------------------------------------------------------------------------


@skip_no_ask
class TestMultiTurn:

    def test_today_then_after_that(self, locale):
        responses = run_dialog(locale, [
            "ask which world where can i ride today",
            "and after that",
        ])
        assert len(responses) >= 2
        assert "todays guest worlds are" in responses[0].lower()
        r1 = responses[1].lower()
        assert "guest worlds will be" in r1 or "don't have next month" in r1
        assert "after what" not in r1

    def test_after_that_chain(self, locale):
        """Multiple 'after that' should keep advancing through the month."""
        responses = run_dialog(locale, [
            "ask which world where can i ride today",
            "and after that",
            "and after that",
        ])
        assert len(responses) >= 3
        for r in responses:
            _assert_no_errors(r)

    def test_date_then_after_that(self, locale):
        """'after that' should work after a WorldOnDateIntent query."""
        responses = run_dialog(locale, [
            "ask which world where can i ride on sunday",
            "and after that",
        ])
        assert len(responses) >= 2
        assert "guest worlds will be" in responses[0].lower()
        r1 = responses[1].lower()
        assert "guest worlds will be" in r1 or "don't have next month" in r1

    def test_tomorrow_then_after_that(self, locale):
        responses = run_dialog(locale, [
            "ask which world what about tomorrow",
            "and after that",
        ])
        assert len(responses) >= 2
        r1 = responses[1].lower()
        assert "guest worlds will be" in r1 or "don't have next month" in r1
        assert "after what" not in r1


# ---------------------------------------------------------------------------
# Cross-intent session — comprehensive smoke test
# ---------------------------------------------------------------------------


@skip_no_ask
class TestCrossIntentSession:
    """Run mixed intents in one session to catch session attribute leakage."""

    def test_full_session(self, locale):
        responses = run_dialog(locale, [
            "ask which world where can i ride today",
            "what about tomorrow",
            "and after that",
            "when is london",
            "what is next",
        ])
        assert len(responses) >= 5
        for r in responses:
            _assert_no_errors(r)

        # Spot-check individual responses
        assert "todays guest worlds are" in responses[0].lower()
        assert "tomorrow" in responses[1].lower() or "don't know" in responses[1].lower()
        assert "london" in responses[3].lower()
