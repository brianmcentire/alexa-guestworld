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
    1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
    7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec",
}


def lambda_handler(event, context):
    # Read challenges calendar URL from SSM
    ssm = boto3.client("ssm", region_name="us-east-1")
    base_url = ssm.get_parameter(Name="/guestworld/challenges-url")["Parameter"]["Value"]

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

    # Fetch next month
    next_month_url = "%s?month=%s&yr=%d" % (base_url, _MONTH_ABBRS[next_month], next_year)
    logger.info("Fetching next month calendar: %s", _MONTH_ABBRS[next_month])
    page_next = requests.get(next_month_url, timeout=30)
    page_next.raise_for_status()
    days_next = parse_challenge_calendar_html(page_next.content)

    if not days_current and not days_next:
        raise ValueError("No challenge calendar data found for either month")

    # Collect unique detail URLs from both months
    detail_urls = set()
    for _, challenges in days_current + days_next:
        for category in ("route", "climb"):
            if category in challenges:
                url = challenges[category].get("detail_url")
                if url:
                    detail_urls.add(url)

    # Fetch route detail pages
    route_details = {}
    for url in detail_urls:
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

    # Write to S3
    s3 = boto3.client("s3")
    s3.put_object(Bucket=S3_BUCKET, Key="WeeklyChallenges.json",
                  Body=json_content, ContentType="application/json", ACL="public-read")
    archive_key = "WeeklyChallenges%04d%02d.json" % (current_year, current_month)
    s3.put_object(Bucket=S3_BUCKET, Key=archive_key,
                  Body=json_content, ContentType="application/json", ACL="public-read")

    months = [k for k in [current_key, next_key] if k in days_by_month]
    return {
        "statusCode": 200,
        "routes_scraped": len(detail_urls),
        "months": months,
        "archive_key": archive_key,
    }
