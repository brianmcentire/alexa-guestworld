"""Shared fixtures and module-level mocking for the test suite.

lambda_function.py and the scraper both execute AWS calls at module level,
so boto3 must be patched *before* those modules are imported.
"""

import importlib
import json
import os
import sys
import types
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Add the lambda directory to sys.path so lambda_function can be imported
# ("lambda" is a Python keyword, so we can't use `from lambda import ...`)
_LAMBDA_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "lambda")
sys.path.insert(0, os.path.abspath(_LAMBDA_DIR))

# ---------------------------------------------------------------------------
# Sample CSV matching the format of GuestWorlds.csv on S3
# ---------------------------------------------------------------------------
SAMPLE_CSV = (
    "paris,1\n"
    "paris,2\n"
    "Yorkshire and Innsbruck,3\n"
    "Yorkshire and Innsbruck,4\n"
    "London and Yorkshire,5\n"
    "London and Yorkshire,6\n"
    "Richmond and London,7\n"
    "Makuri Islands and New York,8\n"
    "Makuri Islands and New York,9\n"
    "New York and Richmond,10\n"
    "New York and Richmond,11\n"
    "paris,12\n"
    "paris,13\n"
    "London and Yorkshire,14\n"
    "London and Yorkshire,15\n"
    "Richmond and London,16\n"
    "Makuri Islands and New York,17\n"
    "Makuri Islands and New York,18\n"
    "New York and Richmond,19\n"
    "New York and Richmond,20\n"
    "Yorkshire and Innsbruck,21\n"
    "Yorkshire and Innsbruck,22\n"
    "London and Yorkshire,23\n"
    "London and Yorkshire,24\n"
    "Richmond and London,25\n"
    "paris,26\n"
    "paris,27\n"
    "Makuri Islands and New York,28\n"
    "Makuri Islands and New York,29\n"
    "New York and Richmond,30\n"
    "New York and Richmond,31\n"
)

# ---------------------------------------------------------------------------
# Build the worldList that the Lambda would produce from SAMPLE_CSV
# ---------------------------------------------------------------------------
_WORLD_LIST = ["IndexZero"]
for _row in SAMPLE_CSV.strip().split("\n"):
    _parts = _row.split(",")
    _WORLD_LIST.append(_parts[0].replace("NEWYORK", "New York"))


# ---------------------------------------------------------------------------
# Sample challenge data matching the format of WeeklyChallenges.json on S3
# ---------------------------------------------------------------------------
SAMPLE_CHALLENGE_JSON = {
    "2026-02": {
        "1": {
            "route": {"name": "Legends and Lava", "xp": 500,
                      "distance_km": 22.5, "distance_mi": 14.0,
                      "elevation_m": 350, "elevation_ft": 1148},
            "climb": {"name": "Hardknott Pass", "xp": 250,
                      "distance_km": 5.0, "distance_mi": 3.1,
                      "elevation_m": 200, "elevation_ft": 656},
        },
        "8": {
            "route": {"name": "Tick Tock", "xp": 600,
                      "distance_km": 40.0, "distance_mi": 24.9,
                      "elevation_m": 500, "elevation_ft": 1640},
            "climb": {"name": "Côte de Pike", "xp": 250,
                      "name_ssml": '<phoneme alphabet="ipa" ph="koʊt də paɪk">Côte de Pike</phoneme>',
                      "distance_km": 1.2, "distance_mi": 0.7,
                      "elevation_m": 89, "elevation_ft": 292},
        },
        "15": {
            "route": {"name": "Waisted 8", "xp": 500},
            "climb": {"name": "Mountain Peak", "xp": 300},
        },
        "22": {
            "route": {"name": "Road to Ruins", "xp": 550,
                      "distance_km": 30.0, "distance_mi": 18.6,
                      "elevation_m": 400, "elevation_ft": 1312},
            "climb": {"name": "Alpe du Zwift", "xp": 350,
                      "distance_km": 12.2, "distance_mi": 7.6,
                      "elevation_m": 1036, "elevation_ft": 3399},
        },
    },
    "2026-03": {
        "1": {
            "route": {"name": "March Route", "xp": 500,
                      "distance_km": 25.0, "distance_mi": 15.5,
                      "elevation_m": 300, "elevation_ft": 984},
            "climb": {"name": "March Climb", "xp": 250},
        },
        "8": {
            "route": {"name": "Spring Ride", "xp": 600},
            "climb": {"name": "Spring Hill", "xp": 300},
        },
    },
}


# ---------------------------------------------------------------------------
# Import lambda_function with boto3.resource mocked so S3 init succeeds
# ---------------------------------------------------------------------------
def _mock_s3_resource(*args, **kwargs):
    """Return a fake S3 resource whose Bucket/Object chain yields SAMPLE_CSV
    and SAMPLE_CHALLENGE_JSON."""
    csv_body = MagicMock()
    csv_body.read.return_value = SAMPLE_CSV.encode("utf-8")

    json_body = MagicMock()
    json_body.read.return_value = json.dumps(SAMPLE_CHALLENGE_JSON).encode("utf-8")

    def _make_obj(key):
        obj = MagicMock()
        if key == "WeeklyChallenges.json":
            obj.get.return_value = {"Body": json_body}
        else:
            obj.get.return_value = {"Body": csv_body}
        return obj

    bucket = MagicMock()
    bucket.Object.side_effect = _make_obj

    resource = MagicMock()
    resource.Bucket.return_value = bucket
    return resource


# Patch boto3.resource globally before importing lambda_function
_boto3_patcher = patch("boto3.resource", side_effect=_mock_s3_resource)
_boto3_patcher.start()

# Now import — module-level code will use the mocked boto3
import lambda_function  # noqa: E402

# Stop the patcher (module init is done; it won't re-run)
_boto3_patcher.stop()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def set_lambda_globals():
    """Return a helper that sets worldList, challengeData, and mocks _get_time_state.

    Usage:
        set_lambda_globals(day=5, lastDayOfMonth=31, worldList=world_list)
        set_lambda_globals(day=5, lastDayOfMonth=31, challengeData=challenge_data)
    """

    original_world_list = lambda_function.worldList
    original_challenge_data = lambda_function.challengeData
    patchers = []

    def _set(day=1, lastDayOfMonth=31, worldList=None, challengeData=None,
             nowInEastern=None, midnightInEastern=None):
        if worldList is not None:
            lambda_function.worldList = worldList
        if challengeData is not None:
            lambda_function.challengeData = challengeData
        now = nowInEastern or datetime(2025, 1, day, 12, 0, 0)
        midnight = midnightInEastern or (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0)
        patcher = patch.object(
            lambda_function, '_get_time_state',
            return_value=(now, day, midnight, lastDayOfMonth))
        patcher.start()
        patchers.append(patcher)

    yield _set

    lambda_function.worldList = original_world_list
    lambda_function.challengeData = original_challenge_data
    for p in patchers:
        p.stop()


@pytest.fixture
def world_list():
    """Pre-built worldList from SAMPLE_CSV (same logic as the Lambda)."""
    return list(_WORLD_LIST)


@pytest.fixture
def challenge_data():
    """Pre-built challengeData from SAMPLE_CHALLENGE_JSON."""
    import copy
    return copy.deepcopy(SAMPLE_CHALLENGE_JSON)


@pytest.fixture
def mock_handler_input():
    """Factory that builds a MagicMock(spec=HandlerInput) suitable for handler tests.

    Parameters:
        intent_name  – e.g. "TodaysWorldIntent"
        request_type – e.g. "LaunchRequest" (defaults to "IntentRequest")
        slot_value   – the resolved GuestWorldName value (for WhenWorldIntent)
        slot_resolution_fails – if True, slot resolution chain raises AttributeError
        date_slot_value – the AMAZON.DATE string value (for WorldOnDateIntent)
        challenge_type – resolved challengeType slot value (for WeeklyChallengeIntent)
        challenge_detail – resolved challengeDetail slot value
        challenge_timeframe – resolved challengeTimeframe slot value
        locale – request locale string (default "en-US")
    """

    def _build(intent_name=None, request_type=None, slot_value=None,
               slot_resolution_fails=False, date_slot_value=None,
               challenge_type=None, challenge_detail=None,
               challenge_timeframe=None, locale="en-US"):
        from ask_sdk_model import Intent, IntentRequest

        hi = MagicMock()

        if request_type:
            # Non-intent request (e.g. LaunchRequest) — plain MagicMock is fine
            hi.request_envelope.request.object_type = request_type
        else:
            # Intent request — the SDK's is_intent_name() checks
            # isinstance(request, IntentRequest), so we use a real object
            intent_obj = Intent(name=intent_name)

            # For WhenWorldIntent, the handler accesses
            #   slots['GuestWorldName'].resolutions.resolutions_per_authority[0]
            #       .values[0].value.name
            # We mock the slots dict to support this chain.
            if slot_value is not None:
                slot = MagicMock()
                slot.resolutions.resolutions_per_authority.__getitem__.return_value \
                    .values.__getitem__.return_value.value.name = slot_value
                intent_obj.slots = {"GuestWorldName": slot}
            elif slot_resolution_fails:
                slot = MagicMock()
                slot.resolutions = None
                intent_obj.slots = {"GuestWorldName": slot}

            # For WorldOnDateIntent, set the requestedDate slot value
            if date_slot_value is not None:
                date_slot = MagicMock()
                date_slot.value = date_slot_value
                if intent_obj.slots is None:
                    intent_obj.slots = {}
                intent_obj.slots["requestedDate"] = date_slot

            # For WeeklyChallengeIntent, set challenge slots
            if challenge_type is not None or challenge_detail is not None or challenge_timeframe is not None:
                if intent_obj.slots is None:
                    intent_obj.slots = {}
                for slot_name, slot_val in [("challengeType", challenge_type),
                                             ("challengeDetail", challenge_detail),
                                             ("challengeTimeframe", challenge_timeframe)]:
                    if slot_val is not None:
                        s = MagicMock()
                        s.resolutions.resolutions_per_authority.__getitem__.return_value \
                            .values.__getitem__.return_value.value.name = slot_val
                        intent_obj.slots[slot_name] = s
                    else:
                        s = MagicMock()
                        s.resolutions = None
                        intent_obj.slots[slot_name] = s

            request_obj = IntentRequest(intent=intent_obj, locale=locale)
            hi.request_envelope.request = request_obj

        # session attributes as a real dict so handlers can read/write keys
        hi.attributes_manager.session_attributes = {}

        # response_builder with fluent chain
        response_obj = MagicMock(name="response")
        builder = MagicMock()
        builder.speak.return_value = builder
        builder.ask.return_value = builder
        builder.response = response_obj
        hi.response_builder = builder

        return hi

    return _build
