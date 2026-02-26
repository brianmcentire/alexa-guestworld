# AGENTS.md

Operational guide for coding agents working in this repository.

## Project Snapshot

- Alexa skill: "Guest World Calendar" for Zwift worlds and weekly challenges.
- Runtime: Python 3 AWS Lambda.
- Main skill logic: `lambda/lambda_function.py`.
- Shared scraper logic: `scrapers/guestworld_scraper_core.py` and `scrapers/challenge_scraper_core.py`.
- Scraper Lambda handlers: `scrapers/guestworld_scraper_handler.py` and `scrapers/challenge_scraper_handler.py`.
- Tests: `tests/` (unit + integration + e2e).

## Source Of Truth

- Follow architecture and domain rules in `CLAUDE.md`.
- If this file conflicts with code/tests, prefer current code/tests.
- If this file conflicts with `CLAUDE.md`, follow `CLAUDE.md` for domain behavior.

## Local Environment Setup

- Create virtualenv:
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`
- Install dev deps:
  - `pip install -r requirements-dev.txt`
- Install runtime deps if needed for local execution:
  - `pip install -r lambda/requirements.txt`
  - `pip install -r scrapers/requirements.txt`

## Build, Lint, Test Commands

There is no dedicated lint config (no ruff/flake8/pylint config in repo).
Use pytest as the authoritative quality gate.

- Run default test suite (fast tests only):
  - `pytest -v`
  - Notes: `pyproject.toml` excludes `integration` and `e2e` markers by default.

- Run all unit-style tests explicitly:
  - `pytest tests -v -m "not integration and not e2e"`

- Run integration tests (real AWS + live website):
  - `pytest tests -v -m integration`
  - Requires AWS credentials and SSM access in `us-east-1`.

- Run e2e tests (ASK CLI dialog replay):
  - `pytest tests/test_e2e.py -v -m e2e`
  - Requires ASK CLI installed and authenticated.

- Run a single test file:
  - `pytest tests/test_scraper.py -v`

- Run a single test class:
  - `pytest tests/test_scraper.py::TestParseCalendarHtml -v`

- Run a single test function:
  - `pytest tests/test_scraper.py::TestParseCalendarHtml::test_parses_two_days -v`

- Run tests by keyword expression:
  - `pytest tests -v -k "watopia and not e2e"`

- Stop on first failure:
  - `pytest tests -v -x`

- Build scraper Lambda deployment zip:
  - `bash scrapers/build.sh`
  - Output: `scrapers/build/scraper-lambda.zip`

## Test Strategy Conventions

- Fast parser/handler tests should not call real AWS or network.
- Use mocks for `boto3` and `requests` in unit tests.
- Put integration coverage behind `@pytest.mark.integration`.
- Put ASK CLI dialog replay behind `@pytest.mark.e2e`.
- Keep fixtures in `tests/conftest.py` when reused.
- Preserve regression tests for NLU routing edge cases across locales.

## Python Style Guidelines

### Imports

- Group imports in this order: stdlib, third-party, local modules.
- Prefer one import per line for `from x import y` when readable.
- Keep import style consistent with surrounding file.
- Avoid dynamic imports unless needed for lazy loading or circular breaks.

### Formatting

- Follow PEP 8 style (4 spaces, readable line lengths).
- Match existing formatting in touched files before introducing new style patterns.
- Use blank lines between top-level functions/classes.
- Keep expressions straightforward; favor clarity over compactness.

### Types And Signatures

- Repository currently uses minimal typing.
- Add type hints when they improve clarity, but do not force full annotation rewrites.
- Keep function signatures stable unless behavior change requires updates.
- In core parsing functions, document expected input/output clearly in docstrings.

### Naming

- Functions/variables: `snake_case`.
- Constants: `UPPER_SNAKE_CASE`.
- Test classes: `Test...`; test methods: `test_...`.
- Intent handler classes follow Alexa SDK pattern: `<IntentName>Handler`.

### Docstrings And Comments

- Add docstrings for new modules and non-trivial functions.
- Keep comments focused on intent or edge cases, not obvious code narration.
- Preserve existing section separators in long files when adding related code.

## Error Handling And Logging

- Fail loudly for invalid scraper input in handlers (raise `ValueError` for empty parsed data).
- For network calls, keep timeouts explicit (`requests.get(..., timeout=...)`).
- In scraper detail-page loops, degrade gracefully on per-item failure and continue.
- Log operational context with `logger.info` and failures with stack traces where useful.
- In Alexa handler paths, return user-friendly speech for recoverable runtime issues.

## Alexa-Specific Behavioral Rules

- Treat timezone as `America/New_York` for day-boundary logic.
- Keep multi-turn behavior by using `.ask(" ")` on normal success responses.
- Preserve handler registration order; `IntentReflectorHandler` must remain last.
- Keep Watopia special-case behavior in `WhenWorldIntentHandler`.
- Keep locale-aware units for weekly challenge responses.

## Data And AWS Conventions

- S3 bucket: `guestworldskill`.
- Guest world source URL from SSM: `/guestworld/scraper-url`.
- Challenge source URL from SSM: `/guestworld/challenges-url`.
- Primary objects:
  - `GuestWorlds.csv`
  - `WeeklyChallenges.json`
- Archive naming conventions:
  - `GuestWorldsYYYYMM.csv`
  - `WeeklyChallengesYYYYMM.json`

## Interaction Model Conventions

- Keep locale models aligned across `interactionModels/custom/en-*.json` unless locale-specific differences are intentional.
- Preserve intent/slot naming compatibility expected by `lambda/lambda_function.py`.
- When changing utterances, consider cross-intent disambiguation and date phrasing collisions.

## Rules File Check (Cursor/Copilot)

- Checked for Cursor rules in `.cursor/rules/` and `.cursorrules`: none found.
- Checked for Copilot rules in `.github/copilot-instructions.md`: none found.
- If such files are added later, treat them as additional agent instructions.

## Safe Change Workflow

- Read existing tests for the area before editing behavior.
- Make minimal, targeted changes.
- Run focused tests first, then broader suites as needed.
- Do not silently change public response wording without updating tests.
- Keep external side effects (AWS/network) mocked in default test runs.
