# Project Analysis: Alexa Guest World Calendar

## Project Overview

An Alexa Skill that helps Zwift users (indoor cyclists and runners) quickly check which virtual worlds are currently available and when specific worlds will be active next. Published in the Alexa Store with users worldwide.

**Invocation:** "Alexa, ask Which World..."

**Example queries:**
- "Where can I ride today?"
- "When can I run in London?"
- "What guest world is next?"
- "Where can I ride tomorrow?"

## Current Architecture

### AWS Account Layout

The project spans two AWS accounts:
- **Infrastructure account** — EC2 scraper, S3 bucket, SSM parameters
- **Alexa-managed account** — Lambda function (provisioned by Alexa Skills Kit), reads from S3 cross-account

### Components

1. **Alexa Skill Interface**
   - Supports multiple English locales: en-US, en-CA, en-GB, en-AU
   - Interaction models define intents and slot types for natural language processing
   - Published in Alexa Store for US, CA, AU, IE, VI, VG, GB, NZ

2. **AWS Lambda Function** (`lambda/lambda_function.py`)
   - Python-based handler using Alexa Skills Kit SDK
   - Runs in the Alexa-managed account; reads calendar data from S3 cross-account
   - Uses Eastern timezone (America/New_York) for day calculations
   - World changes happen at midnight Eastern time (9pm Pacific)

3. **Data Storage**
   - S3 bucket: `guestworldskill` (infrastructure account)
   - File: `GuestWorlds.csv`
   - Format: `world_name(s),day_number`

4. **Data Collection**
   - Python scraper (`guest-world-scraper/getCalendar-writesToStdout.py`)
   - Scrapes schedule from source URL (configured in SSM parameter `/guestworld/scraper-url`)
   - Parses JSON calendar data from page
   - Outputs CSV format to stdout

5. **Automation**
   - EC2 instance (`GuestWorldS3Updater`) runs at 11:55pm on last day of each month
   - IAM role `GuestWorldS3UpdaterEC2Role` provides S3 write and SSM read access
   - Processes new calendar for upcoming month
   - Uploads two files to S3:
     - `GuestWorlds.csv` (generic name, used by Lambda)
     - `GuestWorlds[YYYYMM].csv` (timestamped archive copy)

### Supported Intents

- **TodaysWorldIntent** - Current active worlds
- **TomorrowsWorldIntent** - Tomorrow's worlds
- **WhenWorldIntent** - When a specific world will be available
- **NextWorldIntent** - When worlds will change next
- **ZwiftTimeIntent** - Debug intent for day number
- **HelpIntent** - Usage instructions
- **CancelOrStopIntent** - Exit skill

### Supported Worlds

Guest worlds (rotate on schedule):
- Paris
- Yorkshire
- Innsbruck
- London
- Richmond
- Makuri Islands
- New York

Always available:
- Watopia (not in CSV, handled as special case)

## Data Format Analysis

### CSV Structure

Sample from January 2026:
```
paris,1
paris,2
Yorkshire and Innsbruck,3
Yorkshire and Innsbruck,4
London and Yorkshire,5
London and Yorkshire,6
Richmond and London,7
Makuri Islands and New York,8
```

**Format rules:**
- Single world: lowercase (e.g., `paris`)
- Multiple worlds: proper case, separated by " and " (e.g., `Yorkshire and Innsbruck`)
- Day numbers: 1-31 matching calendar days
- Schedule is arbitrary - worlds can stay active for 2 days, weeks, or longer (no predictable pattern)

**Legacy format issue:**
- Lambda code expects `NEWYORK` (all caps, no space) and converts to "New York"
- Current CSV uses "New York" directly in combinations
- This may cause matching issues in `WhenWorldIntent` handler

## Known Issues & Limitations

1. **Manual monthly updates required**
   - Scraper must be run manually or via scheduled EC2 instance
   - Would prefer direct API integration with Zwift

2. **End-of-month edge cases**
   - Lambda doesn't know next month's schedule
   - Returns "I don't know next month's schedule yet" message
   - Scraper has commented code for handling month transitions

3. **Data format inconsistency**
   - Lambda expects `NEWYORK`, CSV has `New York`
   - String replacement logic may not work correctly with current format

4. **Timezone complexity**
   - Uses Eastern timezone for calculations
   - Edge cases when Eastern is on day 1 but UTC time is still on last day of previous month

5. **Limited error handling**
   - Generic error message for all failures
   - No validation of CSV data format

## Technical Stack

- **Language:** Python 3
- **Alexa SDK:** ask-sdk-core
- **AWS Services:** Lambda, S3, EC2, SSM Parameter Store
- **Dependencies:**
  - boto3 (AWS SDK)
  - python-dateutil
  - lxml (for web scraping)
  - requests

## Deployment

- Lambda function: hosted in Alexa-managed account (us-east-1), provisioned by Alexa Skills Kit
- S3 bucket: `guestworldskill` (infrastructure account)
- SSM parameter: `/guestworld/scraper-url` (infrastructure account, us-east-1)

## User Feedback

- Published in Alexa Store with users worldwide
- Developer's preferred method for checking ride options
- Free to use, no account or special hardware required

## Future Improvement Opportunities

(To be defined in planning phase)
