# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Alexa Skill ("Guest World Calendar") that tells Zwift users which virtual worlds are active today, tomorrow, or when a specific world will be available next. Invoked with "Alexa, ask Which World..." and published in the Alexa Store across 8 countries.

## Architecture

**Lambda function** (`lambda/lambda_function.py`) — Python 3, uses `ask-sdk-core`. All state is initialized at module level (Lambda cold start): reads a CSV from S3 bucket `guestworldskill` into a `worldList` array indexed by day-of-month. Intent handlers reference these globals.

**Key timezone detail:** Zwift's guest world changeover happens at 8 PM Los Angeles time, which is midnight in Halifax (UTC-4). All day calculations use `America/Halifax` timezone.

**Intent handlers** (registered in order, IntentReflectorHandler must be last):
- `TodaysWorldIntentHandler` — returns `worldList[dayNumber]`
- `TomorrowsWorldIntentHandler` — returns next day's worlds, with end-of-month edge case
- `WhenWorldIntentHandler` — searches forward in `worldList` for a named world; uses case-insensitive, space-stripped matching. Watopia is always available (hardcoded special case)
- `NextWorldIntentHandler` — finds when worlds change next; calculates hours/minutes until midnight Halifax for next-day changes
- `ZwiftTimeIntentHandler` — debug intent, returns current Halifax day number

**Interaction models** (`interactionModels/custom/en-*.json`) — four locale variants (en-US, en-CA, en-AU, en-GB), identical structure. The `GuestWorldName` slot uses `AMAZON.AT_CITY` type with extensive synonyms for voice recognition of world names.

**Guest world scraper** (`guest-world-scraper/`):
- `getCalendar-writesToStdout.py` — scrapes the schedule source (URL configured in SSM parameter `/guestworld/scraper-url`), extracts JSON from `<script id="calendar-data">`, outputs `WORLDNAME,day` to stdout
- `getCal` — bash wrapper that pipes scraper through `sed` to expand single world names into paired world availability (e.g., `FRANCE` → `France and Paris`)
- Output: `GuestWorlds.csv` uploaded to S3; archived copies use `GuestWorlds[YYYYMM].csv` naming

**Monthly data refresh:** An EC2 instance runs the scraper at 11:55 PM on the last day of each month, uploads to S3. The Lambda reads this CSV on cold start.

## AWS Account Layout

The project spans two AWS accounts:
- **Infrastructure account** — owns the EC2 scraper instance, S3 bucket (`guestworldskill`), and SSM parameters. The EC2 instance role (`GuestWorldS3UpdaterEC2Role`) has S3 write and SSM read permissions.
- **Alexa-managed account** — hosts the Lambda function, provisioned by the Alexa Skills Kit. Reads from the S3 bucket in the infrastructure account cross-account.

## Data Flow

```
Schedule source → scraper (EC2, monthly) → GuestWorlds.csv (S3, infrastructure account)
                                                       ↓ (cross-account read)
User → Alexa → Lambda cold start reads CSV → worldList[day] → spoken response
```

## Supported Worlds

Rotating: Paris, Yorkshire, Innsbruck, London, Richmond, Makuri Islands, New York
Always available: Watopia (not in CSV, hardcoded in WhenWorldIntentHandler)

## Key Files

- `lambda/lambda_function.py` — all skill logic, handler registration, S3 data loading
- `lambda/utils.py` — S3 presigned URL helper (unused by main handler)
- `lambda/requirements.txt` — `boto3==1.9.216`, `ask-sdk-core==1.11.0`
- `skill.json` — Alexa Skill manifest (endpoint ARN, locales, distribution)
- `interactionModels/custom/en-US.json` — canonical interaction model
- `guest-world-scraper/getCal` — scraper pipeline entry point

## Known Edge Cases

- End-of-month: Lambda doesn't know next month's schedule until scraper updates S3
- Scraper toggle: `cal['months'][0]` vs `cal['months'][1]` must be manually switched near month end when next month's data appears
- `lastDayOfMonth` uses `datetime.now()` (system time) while day calculations use Halifax time — potential mismatch around midnight UTC

## Configuration

- **Scraper source URL** — stored in SSM Parameter Store at `/guestworld/scraper-url` (infrastructure account, us-east-1). Set via AWS console or CLI — no URL values are stored in the repo.
- **EC2 IAM role** — `GuestWorldS3UpdaterEC2Role` with policies for S3 write (`GuestWorldScraperS3Access`) and SSM read (`AmazonEC2RoleforSSM`).

## Validation

Verify skill responses against publicly available Zwift guest world calendars.
