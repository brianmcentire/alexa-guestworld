#!/usr/bin/python3

# Connect to schedule source and scrape the GuestWorld information into a simple CSV file saved on S3

import os
import sys

import requests
import boto3

# Allow importing scraper_core from the same directory when run as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guestworld_scraper_core import parse_calendar_html, format_csv

ssm = boto3.client('ssm', region_name='us-east-1')
scraper_url = ssm.get_parameter(Name='/guestworld/scraper-url')['Parameter']['Value']

page = requests.get(scraper_url)

days = parse_calendar_html(page.content)
csv_output = format_csv(days)
if csv_output:
    print(csv_output, end="")
