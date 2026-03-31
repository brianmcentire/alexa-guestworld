"""AWS Lambda handler for the weekly challenge routes scraper.

Reads the challenges calendar URL from SSM, scrapes current and next month,
fetches route detail pages, and writes WeeklyChallenges.json (+ archive) to S3.

Lambda config: handler = challenge_scraper_handler.lambda_handler
"""

import json
import logging
from datetime import datetime

import boto3
import requests

from challenge_scraper_core import (
    parse_challenge_calendar_html,
    parse_route_detail_page,
    build_challenge_json,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

S3_BUCKET = "guestworldskill"

# Abbreviated month names for calendar URL query params
_MONTH_ABBRS = {
    1: "jan",
    2: "feb",
    3: "mar",
    4: "apr",
    5: "may",
    6: "jun",
    7: "jul",
    8: "aug",
    9: "sep",
    10: "oct",
    11: "nov",
    12: "dec",
}


def _previous_month_year(year, month):
    """Return (year, month) for the month immediately before inputs."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _normalize_name(name):
    """Normalize route/climb names for cache lookups."""
    return " ".join((name or "").strip().casefold().split())


def _extract_detail_fields(entry):
    """Extract cached distance/elevation fields from a challenge entry."""
    detail = {}
    for key in ("distance_km", "distance_mi", "elevation_m", "elevation_ft"):
        if key in entry:
            detail[key] = entry[key]
    return detail if detail else None


def _build_detail_cache_from_json(payload):
    """Build a name-keyed detail cache from stored challenge JSON payload."""
    cache = {}
    if not isinstance(payload, dict):
        return cache

    for _, month_data in payload.items():
        if not isinstance(month_data, dict):
            continue
        for _, day_data in month_data.items():
            if not isinstance(day_data, dict):
                continue
            for category in ("route", "climb"):
                entry = day_data.get(category)
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                detail = _extract_detail_fields(entry)
                if name and detail:
                    norm = _normalize_name(name)
                    if norm and norm not in cache:
                        cache[norm] = detail
    return cache


def _load_detail_cache_from_s3(s3_client, current_year, current_month):
    """Load cached route/climb detail fields from recent challenge JSON objects."""
    keys = ["WeeklyChallenges.json"]

    prev1_year, prev1_month = _previous_month_year(current_year, current_month)
    prev2_year, prev2_month = _previous_month_year(prev1_year, prev1_month)
    keys.append("WeeklyChallenges%04d%02d.json" % (prev1_year, prev1_month))
    keys.append("WeeklyChallenges%04d%02d.json" % (prev2_year, prev2_month))

    cache = {}
    for key in keys:
        try:
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
            body = response["Body"].read().decode("utf-8")
            payload = json.loads(body)
            loaded = _build_detail_cache_from_json(payload)
            for name_key, detail in loaded.items():
                if name_key not in cache:
                    cache[name_key] = detail
            logger.info("Loaded %d cached entries from %s", len(loaded), key)
        except Exception:
            logger.info("No usable cache data from %s", key)

    return cache


def _extract_month_keys(payload):
    """Return sorted valid month keys present in challenge payload JSON."""
    if not isinstance(payload, dict):
        return []

    keys = []
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        if len(key) == 7 and key[4] == "-" and key[:4].isdigit() and key[5:7].isdigit():
            month_num = int(key[5:7])
            if 1 <= month_num <= 12:
                keys.append(key)
    return sorted(set(keys))


def _is_regression_against_existing(existing_payload, new_payload):
    """True when new payload would lose recent months or day coverage.

    Old months that precede the new payload's earliest month are allowed to
    roll off — that is normal forward progress.  But dropping a month that
    is at or after the new payload's earliest month (e.g. a next-month
    entry the existing file already had) is a regression.  Likewise, fewer
    days within any shared month is a regression.
    """
    existing_months = set(_extract_month_keys(existing_payload))
    new_months = set(_extract_month_keys(new_payload))
    if not new_months:
        return (len(existing_months) > 0), sorted(existing_months)

    earliest_new = min(new_months)
    regressed = []

    # Check for existing months at/after the new range that would be lost
    for month in sorted(existing_months - new_months):
        if month >= earliest_new:
            regressed.append(month)

    # Check for fewer days within shared months
    for month in sorted(existing_months & new_months):
        if len(new_payload[month]) < len(existing_payload[month]):
            regressed.append(month)

    return (len(regressed) > 0), sorted(regressed)


def _safe_write_challenge_json(s3_client, key, json_content, challenge_json):
    """Write S3 object only if it does not reduce month coverage vs existing."""
    try:
        existing_response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
        existing_payload = json.loads(existing_response["Body"].read().decode("utf-8"))
        is_regression, missing_months = _is_regression_against_existing(
            existing_payload, challenge_json
        )
        if is_regression:
            logger.warning(
                "Skipping write to %s because new data is missing existing months: %s",
                key,
                ", ".join(missing_months),
            )
            return False
    except Exception:
        # No existing object (or unreadable object) is treated as safe to write.
        pass

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json_content,
        ContentType="application/json",
        ACL="public-read",
    )
    return True


def lambda_handler(event, context):
    # Read challenges calendar URL from SSM
    ssm = boto3.client("ssm", region_name="us-east-1")
    base_url = ssm.get_parameter(Name="/guestworld/challenges-url")["Parameter"][
        "Value"
    ]

    now = datetime.utcnow()
    current_month = now.month
    current_year = now.year

    # Next month
    if current_month == 12:
        next_month = 1
        next_year = current_year + 1
    else:
        next_month = current_month + 1
        next_year = current_year

    # Fetch current month (default page)
    logger.info("Fetching current month calendar")
    page_current = requests.get(base_url, timeout=30)
    page_current.raise_for_status()
    days_current = parse_challenge_calendar_html(page_current.content)

    # Fetch next month (best effort)
    next_month_url = "%s?month=%s&yr=%d" % (
        base_url,
        _MONTH_ABBRS[next_month],
        next_year,
    )
    logger.info("Fetching next month calendar: %s", _MONTH_ABBRS[next_month])
    days_next = []
    try:
        page_next = requests.get(next_month_url, timeout=30)
        page_next.raise_for_status()
        days_next = parse_challenge_calendar_html(page_next.content)
    except Exception:
        logger.warning("Unable to fetch next month challenge calendar", exc_info=True)
        days_next = []

    if not days_current and not days_next:
        raise ValueError("No challenge calendar data found for either month")

    # Load persistent route/climb detail cache from current + recent S3 JSON
    s3 = boto3.client("s3")
    detail_cache_by_name = _load_detail_cache_from_s3(s3, current_year, current_month)

    # Collect unique detail URLs from both months, mapped to challenge names
    detail_urls = {}
    for _, challenges in days_current + days_next:
        for category in ("route", "climb"):
            if category in challenges:
                url = challenges[category].get("detail_url")
                if url:
                    detail_urls[url] = challenges[category].get("name", "")

    # Fetch route detail pages
    route_details = {}
    cache_hits = 0
    for url, name in detail_urls.items():
        cached_detail = detail_cache_by_name.get(_normalize_name(name))
        if cached_detail:
            route_details[url] = cached_detail
            cache_hits += 1
            continue

        try:
            # Detail URLs may be relative — resolve against base
            if url.startswith("/"):
                # Extract base domain from base_url
                from urllib.parse import urljoin

                full_url = urljoin(base_url, url)
            else:
                full_url = url
            logger.info("Fetching detail page: %s", full_url)
            detail_page = requests.get(full_url, timeout=15)
            detail_page.raise_for_status()
            route_details[url] = parse_route_detail_page(detail_page.content)
        except Exception:
            logger.warning("Failed to fetch detail page: %s", url, exc_info=True)
            route_details[url] = None

    logger.info(
        "Detail cache hits: %d of %d unique detail URLs",
        cache_hits,
        len(detail_urls),
    )

    # Build combined JSON
    current_key = "%04d-%02d" % (current_year, current_month)
    next_key = "%04d-%02d" % (next_year, next_month)

    days_by_month = {}
    if days_current:
        days_by_month[current_key] = days_current
    if days_next:
        days_by_month[next_key] = days_next

    challenge_json = build_challenge_json(days_by_month, route_details)
    json_content = json.dumps(challenge_json, ensure_ascii=False)

    # Write to S3, but avoid overwriting with reduced month coverage.
    wrote_keys = []
    skipped_keys = []

    if _safe_write_challenge_json(
        s3, "WeeklyChallenges.json", json_content, challenge_json
    ):
        wrote_keys.append("WeeklyChallenges.json")
    else:
        skipped_keys.append("WeeklyChallenges.json")

    archive_key = "WeeklyChallenges%04d%02d.json" % (current_year, current_month)
    if _safe_write_challenge_json(s3, archive_key, json_content, challenge_json):
        wrote_keys.append(archive_key)
    else:
        skipped_keys.append(archive_key)

    months = [k for k in [current_key, next_key] if k in days_by_month]
    return {
        "statusCode": 200,
        "routes_scraped": len(detail_urls),
        "detail_cache_hits": cache_hits,
        "months": months,
        "archive_key": archive_key,
        "next_month_available": bool(days_next),
        "wrote_keys": wrote_keys,
        "skipped_keys": skipped_keys,
    }
