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

**Shared scraper module** (`guest-world-scraper/scraper_core.py`) — pure functions for parsing schedule HTML using BeautifulSoup4:
- `parse_calendar_html(html_content)` → `list[(day_number, [world_names])]`
- `format_csv(days)` → CSV string with `"World1 and World2,N\n"` lines

**CLI scraper** (`guest-world-scraper/getCalendar-writesToStdout.py`) — thin wrapper: reads URL from SSM, fetches HTML, calls `parse_calendar_html()` + `format_csv()`, prints to stdout.

**Scraper Lambda** (`scraper-lambda/scraper_handler.py`) — Lambda function that scrapes and writes directly to S3:
- Reads URL from SSM `/guestworld/scraper-url`
- Calls shared `parse_calendar_html()` + `format_csv()`
- Writes `GuestWorlds.csv` (primary) and `GuestWorlds{YYYYMM}.csv` (archive) to S3
- Handler: `scraper_handler.lambda_handler`
- Build: `scraper-lambda/build.sh` creates deployment zip

**Monthly data refresh:** EventBridge scheduler invokes the scraper Lambda on the last day of each month. The Alexa Lambda reads the CSV on cold start.

## AWS Account Layout

The project spans two AWS accounts:
- **Infrastructure account** — owns the scraper Lambda, S3 bucket (`guestworldskill`), and SSM parameters. The scraper Lambda role needs S3 write and SSM read permissions.
- **Alexa-managed account** — hosts the Alexa skill Lambda function, provisioned by the Alexa Skills Kit. Reads from the S3 bucket in the infrastructure account cross-account.

## Data Flow

```
Schedule source → scraper Lambda (monthly) → GuestWorlds.csv (S3, infrastructure account)
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
- `guest-world-scraper/scraper_core.py` — shared parsing logic (BeautifulSoup4)
- `guest-world-scraper/getCalendar-writesToStdout.py` — CLI scraper entry point
- `scraper-lambda/scraper_handler.py` — scraper Lambda handler
- `scraper-lambda/build.sh` — Lambda deployment packaging

## Known Edge Cases

- End-of-month: Alexa Lambda doesn't know next month's schedule until scraper updates S3
- `lastDayOfMonth` uses `datetime.now()` (system time) while day calculations use Halifax time — potential mismatch around midnight UTC

## Configuration

- **Scraper source URL** — stored in SSM Parameter Store at `/guestworld/scraper-url` (infrastructure account, us-east-1). Set via AWS console or CLI — no URL values are stored in the repo.
- **Scraper Lambda** — deployed in infrastructure account. Handler: `scraper_handler.lambda_handler`. Needs IAM permissions for S3 write and SSM read. Timeout: at least 30 seconds.

## Validation

Verify skill responses against publicly available Zwift guest world calendars.
