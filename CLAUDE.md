# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Alexa Skill ("Guest World Calendar") that tells Zwift users which virtual worlds are active today, tomorrow, or when a specific world will be available next. Also reports weekly challenge routes (Route of the Week and Climb of the Week) with XP, distance, and elevation details. Invoked with "Alexa, ask Which World..." and published in the Alexa Store across 8 countries.

## Architecture

**Lambda function** (`lambda/lambda_function.py`) — Python 3, uses `ask-sdk-core`. All state is initialized at module level (Lambda cold start): reads a CSV from S3 bucket `guestworldskill` into a `worldList` array indexed by day-of-month, and reads `WeeklyChallenges.json` into a `challengeData` dict keyed by month and day. Intent handlers reference these globals.

**Key timezone detail:** Zwift's guest world changeover happens at midnight Eastern time (9 PM Pacific). All day calculations use `America/New_York` timezone.

**Intent handlers** (registered in order, IntentReflectorHandler must be last):
- `TodaysWorldIntentHandler` — returns `worldList[dayNumber]`
- `TomorrowsWorldIntentHandler` — returns next day's worlds, with end-of-month edge case
- `WhenWorldIntentHandler` — searches forward in `worldList` for a named world; uses case-insensitive, space-stripped matching. Watopia is always available (hardcoded special case)
- `WeeklyChallengeIntentHandler` — returns route/climb of the week info (name, XP, distance, elevation). Supports timeframes (this week, next week, this month, next month). Uses SSML phoneme tags for non-English route names. Locale-aware units (imperial for en-US, metric for others).
- `NextWorldIntentHandler` — finds when worlds change next; calculates hours/minutes until midnight Eastern for next-day changes
- `ZwiftTimeIntentHandler` — debug intent, returns current Eastern time day number

**Interaction models** (`interactionModels/custom/en-*.json`) — four locale variants (en-US, en-CA, en-AU, en-GB), identical structure. The `GuestWorldName` slot uses `AMAZON.AT_CITY` type with extensive synonyms for voice recognition of world names. The `optionalWatopiaIntentTimeframeSlot` is used for utterance matching only — the handler doesn't read its value despite the Watopia-specific name.

**Multi-turn sessions:** All success response paths use `.ask(" ")` (space as reprompt) to keep the session open for follow-up questions. Alexa listens briefly, then auto-closes silently if the user says nothing. Debug intents (ZwiftTime, IntentReflector) do not use multi-turn.

**Utterance design:** Alexa NLU automatically normalizes contractions ("what's" → "what is"), so sample utterances use expanded forms. Cross-intent disambiguation relies on different temporal markers (optionalToday slots vs literal "tomorrow" vs AMAZON.DATE) and different slot types (GuestWorldName city names vs worldReference generic terms).

**Shared scraper module** (`scrapers/guestworld_scraper_core.py`) — pure functions for parsing guest world schedule HTML using BeautifulSoup4:
- `parse_calendar_html(html_content)` → `list[(day_number, [world_names])]`
- `format_csv(days)` → CSV string with `"World1 and World2,N\n"` lines

**Challenge scraper module** (`scrapers/challenge_scraper_core.py`) — pure functions for parsing weekly challenge calendar HTML:
- `parse_challenge_calendar_html(html_content)` → `list[(day_number, {"route": {...}, "climb": {...}})]`
- `parse_route_detail_page(html_content)` → `{"distance_km", "distance_mi", "elevation_m", "elevation_ft"}` or `None`
- `build_challenge_json(days_by_month, route_details)` → combined JSON dict with SSML phonetic hints
- `PHONETIC_OVERRIDES` dict maps tricky route names to SSML phoneme tags

**CLI scraper** (`scrapers/getCalendar-writesToStdout.py`) — thin wrapper: reads URL from SSM, fetches HTML, calls `parse_calendar_html()` + `format_csv()`, prints to stdout.

**Guest world scraper Lambda** (`scrapers/guestworld_scraper_handler.py`) — Lambda function that scrapes and writes directly to S3:
- Reads URL from SSM `/guestworld/scraper-url`
- Calls shared `parse_calendar_html()` + `format_csv()`
- Writes `GuestWorlds.csv` (primary) and `GuestWorlds{YYYYMM}.csv` (archive) to S3
- Handler: `guestworld_scraper_handler.lambda_handler`
- Build: `scrapers/build.sh` creates deployment zip

**Challenge scraper Lambda** (`scrapers/challenge_scraper_handler.py`) — scrapes weekly challenge routes:
- Reads URL from SSM `/guestworld/challenges-url`
- Fetches current and next month calendars, plus route detail pages
- Writes `WeeklyChallenges.json` (primary) and `WeeklyChallenges{YYYYMM}.json` (archive) to S3
- Handler: `challenge_scraper_handler.lambda_handler`
- Classifies entries as route (`category_367`, `/route/` URL) or climb (`category_370`, `/portal/` URL)

**Monthly data refresh:** EventBridge scheduler invokes the guest world scraper Lambda on the last day of each month. The challenge scraper runs weekly (Mondays). The Alexa Lambda reads both data files on cold start.

## AWS Account Layout

The project spans two AWS accounts:
- **Infrastructure account** — owns the scraper Lambda, S3 bucket (`guestworldskill`), and SSM parameters. The scraper Lambda role needs S3 write and SSM read permissions.
- **Alexa-managed account** — hosts the Alexa skill Lambda function, provisioned by the Alexa Skills Kit. Reads from the S3 bucket in the infrastructure account cross-account.

## Data Flow

```
Schedule source → guest world scraper Lambda (monthly) → GuestWorlds.csv (S3)
                                                                    ↓ (cross-account read)
User → Alexa → Lambda cold start reads CSV + JSON → worldList[day] → spoken response
                                                                    ↑ (cross-account read)
Challenge source → challenge scraper Lambda (weekly) → WeeklyChallenges.json (S3)
```

## Supported Worlds

Rotating: Paris, Yorkshire, Innsbruck, London, Richmond, Makuri Islands, New York, Scotland, France
Always available: Watopia (not in CSV, hardcoded in WhenWorldIntentHandler)

## Key Files

- `lambda/lambda_function.py` — all skill logic, handler registration, S3 data loading
- `lambda/utils.py` — S3 presigned URL helper (unused by main handler)
- `lambda/requirements.txt` — `boto3==1.9.216`, `ask-sdk-core==1.11.0`
- `skill.json` — Alexa Skill manifest (endpoint ARN, locales, distribution)
- `interactionModels/custom/en-US.json` — canonical interaction model
- `scrapers/guestworld_scraper_core.py` — shared guest world parsing logic (BeautifulSoup4)
- `scrapers/challenge_scraper_core.py` — shared challenge parsing logic (BeautifulSoup4)
- `scrapers/getCalendar-writesToStdout.py` — CLI scraper entry point
- `scrapers/guestworld_scraper_handler.py` — guest world scraper Lambda handler
- `scrapers/challenge_scraper_handler.py` — challenge scraper Lambda handler
- `scrapers/build.sh` — Lambda deployment packaging (both scrapers)

## Known Edge Cases

- End-of-month: Alexa Lambda doesn't know next month's schedule until scraper updates S3
- `lastDayOfMonth` uses `datetime.now()` (system time) while day calculations use Eastern time — potential mismatch around midnight UTC

## Configuration

- **Guest world scraper URL** — stored in SSM Parameter Store at `/guestworld/scraper-url` (infrastructure account, us-east-1). Set via AWS console or CLI — no URL values are stored in the repo.
- **Challenge scraper URL** — stored in SSM at `/guestworld/challenges-url`. Same pattern — no URL in code or docs.
- **Guest world scraper Lambda** — deployed in infrastructure account. Handler: `guestworld_scraper_handler.lambda_handler`. Needs IAM permissions for S3 write and SSM read. Timeout: at least 30 seconds.
- **Challenge scraper Lambda** — deployed in infrastructure account. Handler: `challenge_scraper_handler.lambda_handler`. Same IAM permissions. Timeout: at least 60 seconds (fetches multiple detail pages).

## Validation

Verify skill responses against publicly available Zwift guest world calendars.
