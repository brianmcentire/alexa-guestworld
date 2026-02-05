#!/usr/bin/python3

# Connect to schedule source and scrape the GuestWorld information into a simple CSV file saved on S3

from lxml import html
import requests
import boto3

ssm = boto3.client('ssm', region_name='us-east-1')
scraper_url = ssm.get_parameter(Name='/guestworld/scraper-url')['Parameter']['Value']

page = requests.get(scraper_url)
tree = html.fromstring(page.content)

# Find the calendar table and extract day cells with dates
table = tree.xpath('//table[contains(@class, "calendar-table")]')[0]
cells = table.xpath('.//td[contains(@class, "day-with-date")]')

# Collect (day_number, world_names) for each cell
days = []
for cell in cells:
    day_num = cell.xpath('.//span[contains(@class, "day-number")]/text()')
    worlds = cell.xpath('.//span[@class="spiffy-title"]/text()')
    if day_num and worlds:
        days.append((int(day_num[0]), worlds))

days.sort(key=lambda x: x[0])

dayInc = 0
for day_num, worlds in days:
    dayInc += 1
    print(" and ".join(worlds) + "," + str(dayInc))
