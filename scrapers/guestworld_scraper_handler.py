"""AWS Lambda handler for the guest world scraper.

Reads the schedule URL from SSM, scrapes the calendar, and writes
GuestWorlds.csv (+ monthly archive) to S3.

Lambda config: handler = guestworld_scraper_handler.lambda_handler
"""

from datetime import datetime

import boto3
import requests

from guestworld_scraper_core import parse_calendar_html, format_csv

S3_BUCKET = "guestworldskill"


def lambda_handler(event, context):
    # Read scraper URL from SSM
    ssm = boto3.client("ssm", region_name="us-east-1")
    scraper_url = ssm.get_parameter(Name="/guestworld/scraper-url")["Parameter"]["Value"]

    # Fetch and parse
    page = requests.get(scraper_url, timeout=30)
    page.raise_for_status()

    days = parse_calendar_html(page.content)
    if not days:
        raise ValueError("No calendar data found on the schedule page")

    csv_content = format_csv(days)

    # Calculate archive key — named for the current month being scraped
    now = datetime.utcnow()
    archive_suffix = now.strftime("%Y%m")

    # Write to S3
    s3 = boto3.client("s3")
    s3.put_object(Bucket=S3_BUCKET, Key="GuestWorlds.csv", Body=csv_content, ACL="public-read")
    s3.put_object(Bucket=S3_BUCKET, Key=f"GuestWorlds{archive_suffix}.csv", Body=csv_content, ACL="public-read")

    return {
        "statusCode": 200,
        "days_scraped": len(days),
        "archive_key": f"GuestWorlds{archive_suffix}.csv",
    }
