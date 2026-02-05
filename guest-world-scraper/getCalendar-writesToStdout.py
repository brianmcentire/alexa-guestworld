#!/usr/bin/python3

# Connect to schedule source and scrap the GuestWorld information into a simple CSV file saved on S3

from lxml import html
import requests
import json
import boto3

ssm = boto3.client('ssm', region_name='us-east-1')
scraper_url = ssm.get_parameter(Name='/guestworld/scraper-url')['Parameter']['Value']

page = requests.get(scraper_url)
tree = html.fromstring(page.content)
schedule = tree.xpath('//script[@id="calendar-data"]/text()')
cal=json.loads(schedule[0])

dayInc=0
for week in range(0,6):
  for day in range(0,7):

## Note on the last day(s) of the month, the next months calendar becomes
## available in the tree as months(1) but for most of the month, say
## from the first day until the second to last or so it is in months(0)

    world = cal['months'][0]['weeks'][week]['days'][day]['map']
##    world = cal['months'][1]['weeks'][week]['days'][day]['map']
    if world:
      dayInc += 1
      print (str(world) + "," + str(dayInc))
