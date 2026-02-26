"""AWS Lambda handler for the guest world scraper.

Reads the schedule URL from SSM, scrapes the calendar, and writes
GuestWorlds.csv (+ monthly archives) to S3.

Lambda config: handler = guestworld_scraper_handler.lambda_handler
"""

from datetime import datetime
import logging

import boto3
import requests

from guestworld_scraper_core import parse_calendar_html, format_csv

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


def lambda_handler(event, context):
    # Read scraper URL from SSM
    ssm = boto3.client("ssm", region_name="us-east-1")
    base_url = ssm.get_parameter(Name="/guestworld/scraper-url")["Parameter"]["Value"]

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

    # Fetch and parse current month (default page)
    page = requests.get(base_url, timeout=30)
    page.raise_for_status()
    days_current = parse_calendar_html(page.content)
    if not days_current:
        raise ValueError("No calendar data found on the schedule page")

    csv_current = format_csv(days_current)

    # Try to fetch next month. If unavailable, continue with current month only.
    days_next = []
    next_month_url = "%s?month=%s&yr=%d" % (
        base_url,
        _MONTH_ABBRS[next_month],
        next_year,
    )
    try:
        logger.info("Fetching next month calendar: %s", _MONTH_ABBRS[next_month])
        page_next = requests.get(next_month_url, timeout=30)
        page_next.raise_for_status()
        days_next = parse_calendar_html(page_next.content)
    except Exception:
        logger.warning("Unable to fetch next month calendar", exc_info=True)
        days_next = []

    # Calculate archive key — named for the current month being scraped
    current_archive_suffix = "%04d%02d" % (current_year, current_month)
    current_archive_key = f"GuestWorlds{current_archive_suffix}.csv"

    # Write to S3
    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=S3_BUCKET, Key="GuestWorlds.csv", Body=csv_current, ACL="public-read"
    )
    s3.put_object(
        Bucket=S3_BUCKET, Key=current_archive_key, Body=csv_current, ACL="public-read"
    )

    next_archive_key = None
    if days_next:
        csv_next = format_csv(days_next)
        next_archive_suffix = "%04d%02d" % (next_year, next_month)
        next_archive_key = f"GuestWorlds{next_archive_suffix}.csv"
        s3.put_object(
            Bucket=S3_BUCKET, Key=next_archive_key, Body=csv_next, ACL="public-read"
        )

    return {
        "statusCode": 200,
        "days_scraped": len(days_current),
        "archive_key": current_archive_key,
        "next_month_available": bool(days_next),
        "next_archive_key": next_archive_key,
    }
