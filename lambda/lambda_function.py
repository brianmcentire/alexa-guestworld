# -*- coding: utf-8 -*-

# This sample demonstrates handling intents from an Alexa skill using the Alexa Skills Kit SDK for Python.
# Please visit https://alexa.design/cookbook for additional examples on implementing slots, dialog management,
# session persistence, api calls, and more.
# This sample is built using the handler classes approach in skill builder.
import json
import logging
import re
import ask_sdk_core.utils as ask_utils
from datetime import datetime
from datetime import timedelta
from dateutil import tz
import boto3
import calendar

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model import Response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Time and data helpers
# ---------------------------------------------------------------------------

def _get_time_state():
    """Return fresh (now, day, midnight, last_day) for the current invocation."""
    now = datetime.now(tz.gettz('America/New_York'))
    day = now.day
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
    last_day = calendar.monthrange(now.year, now.month)[1]
    return now, day, midnight, last_day


def _data_unavailable_response(handler_input):
    """If worldList failed to load, return a friendly error response."""
    if worldList is None:
        speak = ("Sorry, the Guest World calendar is temporarily unavailable. "
                 "Please try again later.")
        return handler_input.response_builder.speak(speak).response
    return None


def _ordinal_date_string(dt):
    """Return a spoken date like 'February the 17th'."""
    day = dt.day
    if 11 <= day <= 13:
        suffix = "th"
    elif day % 10 == 1:
        suffix = "st"
    elif day % 10 == 2:
        suffix = "nd"
    elif day % 10 == 3:
        suffix = "rd"
    else:
        suffix = "th"
    return dt.strftime("%B") + " the " + str(day) + suffix


def _parse_amazon_date(date_str, now):
    """Parse an AMAZON.DATE slot value into a list of (day_number, datetime) tuples.

    Only returns days within the current month. Returns [] for unparseable or
    out-of-range values.
    """
    if not date_str:
        return []

    last_day = calendar.monthrange(now.year, now.month)[1]

    # Weekend format: YYYY-Www-WE → Saturday + Sunday of that ISO week
    m = re.match(r'^(\d{4})-W(\d{1,2})-WE$', date_str)
    if m:
        year, week = int(m.group(1)), int(m.group(2))
        try:
            saturday = datetime.strptime(f"{year}-W{week:02d}-6", "%G-W%V-%u")
            sunday = datetime.strptime(f"{year}-W{week:02d}-7", "%G-W%V-%u")
        except ValueError:
            return []
        results = []
        for d in [saturday, sunday]:
            if d.year == now.year and d.month == now.month and 1 <= d.day <= last_day:
                results.append((d.day, d))
        return results

    # Recurring day-of-month: XXXX-XX-DD (e.g. "the twenty seventh")
    m = re.match(r'^XXXX-XX-(\d{2})$', date_str)
    if m:
        d = int(m.group(1))
        if 1 <= d <= last_day:
            return [(d, now.replace(day=d))]
        return []

    # Specific date: YYYY-MM-DD
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return []

    if dt.year == now.year and dt.month == now.month and 1 <= dt.day <= last_day:
        return [(dt.day, dt)]
    return []


# ---------------------------------------------------------------------------
# S3 data loading
# ---------------------------------------------------------------------------

worldList = None


def _load_world_list():
    """Read the processed calendar from S3 into worldList for quick lookups."""
    global worldList
    try:
        s3 = boto3.resource('s3')
        bucket = s3.Bucket('guestworldskill')
        obj = bucket.Object('GuestWorlds.csv')
        response = obj.get()
        worldList = ["IndexZero"]
        lines = response['Body'].read().decode('utf-8').split('\n')
        for row in lines:
            row = row.split(",")
            worldList.append(row[0].replace("NEWYORK", "New York"))
        logger.info("Loaded %d days of calendar data from S3", len(worldList) - 1)
    except Exception:
        logger.error("Failed to load calendar data from S3", exc_info=True)
        worldList = None


_load_world_list()


challengeData = None


def _load_challenge_data():
    """Read weekly challenge data from S3 JSON."""
    global challengeData
    try:
        s3 = boto3.resource('s3')
        obj = s3.Bucket('guestworldskill').Object('WeeklyChallenges.json')
        response = obj.get()
        challengeData = json.loads(response['Body'].read().decode('utf-8'))
        logger.info("Loaded challenge data from S3")
    except Exception:
        logger.error("Failed to load challenge data from S3", exc_info=True)
        challengeData = None


_load_challenge_data()


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Welcome, you can say. What are todays guest worlds? Where can I ride tomorrow? What's available this weekend? What's Next? Or, when can I run in London?"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class TodaysWorldIntentHandler(AbstractRequestHandler):
    """Handler for Todays World Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("TodaysWorldIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("Handling TodaysWorldIntent")
        error = _data_unavailable_response(handler_input)
        if error:
            return error
        now, day, midnight, last_day = _get_time_state()

        speak_output = "Todays Guest Worlds are " + worldList[day]

        session_attr = handler_input.attributes_manager.session_attributes
        session_attr['last_answered_day'] = day
        session_attr['last_context'] = 'world'

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(" ")
                .response
        )


class TomorrowsWorldIntentHandler(AbstractRequestHandler):
    """Handler for Tomorrows World Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("TomorrowsWorldIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("Handling TomorrowsWorldIntent")
        error = _data_unavailable_response(handler_input)
        if error:
            return error
        now, day, midnight, last_day = _get_time_state()

        session_attr = handler_input.attributes_manager.session_attributes

        if day < last_day:
            speak_output = "Tomorrow's Guest Worlds are " + worldList[day + 1]
            session_attr['last_answered_day'] = day + 1
            session_attr['last_context'] = 'world'
        else:
            speak_output = "I don't know next month's schedule yet. " + worldList[day] + " are available today. Ask me again tomorrow."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(" ")
                .response
        )


class WhenWorldIntentHandler(AbstractRequestHandler):
    """Handler for When World Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("WhenWorldIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("Handling WhenWorldIntent")
        error = _data_unavailable_response(handler_input)
        if error:
            return error
        now, day, midnight, last_day = _get_time_state()

        try:
            worldName = handler_input.request_envelope.request.intent.slots['GuestWorldName'].resolutions.resolutions_per_authority[0].values[0].value.name
        except (AttributeError, IndexError, KeyError, TypeError):
            speak = "I didn't catch which world you asked about. Could you try again?"
            return handler_input.response_builder.speak(speak).ask(speak).response


        if worldName == "Watopia":
            speak_output = "Watopia is available today and every day."
        else:
            speak_output = "  "

            lookupDay = day
            # Be sure to compare case insensitive and eliminate white space spaces because of data source words like NEWYORK vs New York
            worldNameToMatch = worldName.casefold().replace(" ","")
            while True:
                if lookupDay > last_day:
                    break
                if worldNameToMatch in worldList[lookupDay].casefold().replace(" ",""):
                    break
                lookupDay += 1

            speak_output += worldName
            if (lookupDay == day):
                speak_output += " is available now."
            elif lookupDay > last_day:
                speak_output += " won't be available until sometime next month."
            elif (lookupDay - day) == 1:
                speak_output += " will be available tomorrow."
            else:
                speak_output += (" will be available in " + str(lookupDay - day)
                                 + " days on " + _ordinal_date_string(now.replace(day=lookupDay)) + ".")

            if lookupDay <= last_day:
                session_attr = handler_input.attributes_manager.session_attributes
                session_attr['last_answered_day'] = lookupDay
                session_attr['last_context'] = 'world'


        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(" ")
                .response
        )


class WorldOnDateIntentHandler(AbstractRequestHandler):
    """Handler for World On Date Intent — answers 'what can I ride on Saturday?'"""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("WorldOnDateIntent")(handler_input)

    def handle(self, handler_input):
        logger.info("Handling WorldOnDateIntent")
        error = _data_unavailable_response(handler_input)
        if error:
            return error
        now, day, midnight, last_day = _get_time_state()

        try:
            date_str = handler_input.request_envelope.request.intent.slots['requestedDate'].value
        except (AttributeError, KeyError, TypeError):
            date_str = None

        dates = _parse_amazon_date(date_str, now)

        if not dates and date_str:
            # Valid slot but different month or unparseable
            speak = "I don't have the schedule for that date. I only have this month's calendar."
            return handler_input.response_builder.speak(speak).ask(" ").response
        elif not dates:
            speak = "I didn't catch which date you asked about. Could you try again?"
            return handler_input.response_builder.speak(speak).ask(speak).response

        # Check for past dates
        past = [(d, dt) for d, dt in dates if d < day]
        future = [(d, dt) for d, dt in dates if d >= day]

        if not future:
            # All requested dates are in the past
            speak = ("The " + _ordinal_date_string(past[0][1]).split("the ", 1)[1]
                     + " has already passed and I don't have next month's calendar yet. "
                     + worldList[day] + " are available today.")
            return handler_input.response_builder.speak(speak).ask(" ").response

        # Filter to only future/today dates
        dates = future
        session_attr = handler_input.attributes_manager.session_attributes

        if len(dates) == 1:
            # Single date
            d, dt = dates[0]
            session_attr['last_answered_day'] = d
            session_attr['last_context'] = 'world'
            speak = "On " + _ordinal_date_string(dt) + ", the guest worlds will be " + worldList[d] + "."
            return handler_input.response_builder.speak(speak).ask(" ").response

        # Weekend (2 dates)
        d1, dt1 = dates[0]
        d2, dt2 = dates[1]
        session_attr['last_answered_day'] = d2
        session_attr['last_context'] = 'world'

        if worldList[d1] == worldList[d2]:
            # Same worlds both days
            # Determine if we need disambiguation (today is weekend and this is NOT this weekend)
            today_is_weekend = now.weekday() >= 5  # 5=Saturday, 6=Sunday
            this_weekend_days = set()
            if today_is_weekend:
                # Find this weekend's Saturday and Sunday
                if now.weekday() == 5:  # Saturday
                    this_weekend_days = {now.day, now.day + 1} if now.day + 1 <= last_day else {now.day}
                else:  # Sunday
                    this_weekend_days = {now.day - 1, now.day} if now.day - 1 >= 1 else {now.day}

            requested_days = {d1, d2}
            if today_is_weekend and requested_days != this_weekend_days:
                # "Next weekend" said on a weekend — need disambiguation
                speak = ("On Saturday and Sunday, " + _ordinal_date_string(dt1)
                         + " and " + _ordinal_date_string(dt2).split("the ", 1)[1]
                         + ", the guest worlds will be " + worldList[d1] + ".")
            else:
                speak = ("This Saturday and Sunday, the guest worlds will be "
                         + worldList[d1] + ".")
            return handler_input.response_builder.speak(speak).ask(" ").response
        else:
            # Different worlds each day
            today_is_weekend = now.weekday() >= 5
            this_weekend_days = set()
            if today_is_weekend:
                if now.weekday() == 5:
                    this_weekend_days = {now.day, now.day + 1} if now.day + 1 <= last_day else {now.day}
                else:
                    this_weekend_days = {now.day - 1, now.day} if now.day - 1 >= 1 else {now.day}

            requested_days = {d1, d2}
            if today_is_weekend and requested_days != this_weekend_days:
                speak = ("On Saturday " + _ordinal_date_string(dt1)
                         + ", the guest worlds will be " + worldList[d1]
                         + ". On Sunday " + _ordinal_date_string(dt2)
                         + ", they will be " + worldList[d2] + ".")
            else:
                speak = ("On Saturday, the guest worlds will be " + worldList[d1]
                         + ". On Sunday, they will be " + worldList[d2] + ".")
            return handler_input.response_builder.speak(speak).ask(" ").response


class AfterThatIntentHandler(AbstractRequestHandler):
    """Handler for After That Intent — answers 'and after that?' follow-ups."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AfterThatIntent")(handler_input)

    def handle(self, handler_input):
        logger.info("Handling AfterThatIntent")
        now, day, midnight, last_day = _get_time_state()
        session_attr = handler_input.attributes_manager.session_attributes
        last_context = session_attr.get('last_context')

        if last_context == 'challenge':
            return self._handle_challenge_followup(handler_input, session_attr, now)

        # Default: world follow-up
        error = _data_unavailable_response(handler_input)
        if error:
            return error

        last_answered_day = session_attr.get('last_answered_day')

        if last_answered_day is None:
            speak = "After what? Try asking what worlds are available today first."
            return handler_input.response_builder.speak(speak).ask(speak).response

        next_day = last_answered_day + 1
        while next_day <= last_day and worldList[next_day] == worldList[last_answered_day]:
            next_day += 1

        if next_day > last_day:
            speak = "I don't have next month's schedule yet."
            return handler_input.response_builder.speak(speak).ask(" ").response

        session_attr['last_answered_day'] = next_day
        speak = ("On " + _ordinal_date_string(now.replace(day=next_day))
                 + ", the guest worlds will be " + worldList[next_day] + ".")

        return (
            handler_input.response_builder
                .speak(speak)
                .ask(" ")
                .response
        )

    def _handle_challenge_followup(self, handler_input, session_attr, now):
        """Handle 'after that' following a challenge query — advance by one week."""
        if challengeData is None:
            speak = ("Sorry, the weekly challenge data is temporarily unavailable. "
                     "Please try again later.")
            return handler_input.response_builder.speak(speak).response

        last_date_str = session_attr.get('last_challenge_date')
        if not last_date_str:
            speak = "After what? Try asking about the route or climb of the week first."
            return handler_input.response_builder.speak(speak).ask(speak).response

        last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
        next_date = last_date + timedelta(days=7)
        month_key = next_date.strftime("%Y-%m")
        month_data = challengeData.get(month_key)

        if month_data is None:
            speak = "I don't have challenge data that far out."
            return handler_input.response_builder.speak(speak).ask(" ").response

        entry, _ = _find_challenge_for_day(month_data, next_date.day)
        if entry is None:
            speak = "I don't have challenge data that far out."
            return handler_input.response_builder.speak(speak).ask(" ").response

        categories = session_attr.get('last_challenge_categories', ['route', 'climb'])
        locale = handler_input.request_envelope.request.locale or "en-US"
        use_imperial = locale.startswith("en-US")

        # Format the response
        parts = []
        for cat in categories:
            if cat not in entry:
                continue
            ch = entry[cat]
            short_label = _challenge_type_label(cat, short=True)
            name = _format_challenge_name(ch)
            overview = "The following week's %s is %s, worth %d XP." % (
                short_label, name, ch["xp"])
            dist = _format_distance(ch, use_imperial)
            elev = _format_elevation(ch, use_imperial)
            if dist and elev:
                overview += " It's %s long with %s of elevation gain." % (dist, elev)
            elif dist:
                overview += " It's %s long." % dist
            elif elev:
                overview += " It has %s of elevation gain." % elev
            parts.append(overview)

        if not parts:
            speak = "I don't have challenge data for that week."
            return handler_input.response_builder.speak(speak).ask(" ").response

        speak = " ".join(parts)
        if _needs_ssml(speak):
            speak = "<speak>" + speak + "</speak>"

        # Update session for further chaining
        session_attr['last_challenge_date'] = next_date.strftime("%Y-%m-%d")

        return (
            handler_input.response_builder
                .speak(speak)
                .ask(" ")
                .response
        )


def _resolve_slot(handler_input, slot_name):
    """Resolve a custom slot value, returning the canonical value or None.

    Tries the resolution authority chain first (gives canonical value),
    then falls back to the raw slot value.
    """
    try:
        slot = handler_input.request_envelope.request.intent.slots[slot_name]
    except (AttributeError, KeyError, TypeError):
        return None
    # Try resolution authority (canonical value)
    try:
        return slot.resolutions.resolutions_per_authority[0].values[0].value.name
    except (AttributeError, IndexError, KeyError, TypeError):
        pass
    # Fall back to raw slot value
    return getattr(slot, 'value', None)


def _find_challenge_for_day(month_data, day):
    """Find the challenge entry active on the given day.

    Challenge entries are keyed by their start day (e.g., "1", "8", "15").
    A challenge is active from its start day until the next entry's start day.
    Returns (entry_dict, start_day) or (None, None).
    """
    if not month_data:
        return None, None
    start_days = sorted(int(d) for d in month_data.keys())
    active_day = None
    for d in start_days:
        if d <= day:
            active_day = d
        else:
            break
    if active_day is None:
        return None, None
    return month_data[str(active_day)], active_day


def _format_challenge_name(entry):
    """Return SSML-wrapped name if phonetic override exists, else plain name."""
    return entry.get("name_ssml", entry["name"])


def _needs_ssml(text):
    """Check if text contains SSML tags and needs <speak> wrapper."""
    return "<phoneme" in text


def _format_distance(entry, use_imperial):
    """Format distance string from entry, or return None if unavailable."""
    if use_imperial and "distance_mi" in entry:
        return "%.1f miles" % entry["distance_mi"]
    elif not use_imperial and "distance_km" in entry:
        return "%.1f kilometers" % entry["distance_km"]
    return None


def _format_elevation(entry, use_imperial):
    """Format elevation string from entry, or return None if unavailable."""
    if use_imperial and "elevation_ft" in entry:
        return "{:,.0f} feet".format(entry["elevation_ft"])
    elif not use_imperial and "elevation_m" in entry:
        return "{:,.0f} meters".format(entry["elevation_m"])
    return None


def _challenge_type_label(category, short=False):
    """Return the spoken label for a challenge category.

    Use short=True when combining with a timeframe like "This week's"
    to avoid "This week's route of the week" redundancy.
    """
    if short:
        return "route" if category == "route" else "climb"
    if category == "route":
        return "route of the week"
    return "climb of the week"


class WeeklyChallengeIntentHandler(AbstractRequestHandler):
    """Handler for Weekly Challenge Intent — route/climb of the week queries."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("WeeklyChallengeIntent")(handler_input)

    def handle(self, handler_input):
        logger.info("Handling WeeklyChallengeIntent")

        if challengeData is None:
            speak = ("Sorry, the weekly challenge data is temporarily unavailable. "
                     "Please try again later.")
            return handler_input.response_builder.speak(speak).response

        now, day, midnight, last_day = _get_time_state()

        challenge_type = _resolve_slot(handler_input, "challengeType")
        challenge_detail = _resolve_slot(handler_input, "challengeDetail")
        challenge_timeframe = _resolve_slot(handler_input, "challengeTimeframe")

        # Determine units based on locale
        locale = handler_input.request_envelope.request.locale or "en-US"
        use_imperial = locale.startswith("en-US")

        current_month_key = now.strftime("%Y-%m")

        # Determine which categories to report
        if challenge_type == "route of the week":
            categories = ["route"]
        elif challenge_type == "climb of the week":
            categories = ["climb"]
        else:
            categories = ["route", "climb"]

        # Handle "when does it change" / "how long until change" queries
        if challenge_detail is None and challenge_type is not None:
            raw_utterance = ""
            try:
                # Check if this is a "when does it change" type query
                # by looking at the intent's raw input
                raw_utterance = handler_input.request_envelope.request.intent.name
            except Exception:
                pass

        # Handle change schedule queries
        # The utterance patterns "when does the {challengeType} change" and
        # "how long until the {challengeType} changes" are matched by having
        # a challengeType but no detail or timeframe
        # We detect this from the utterance text if available

        # --- Determine timeframe and look up data ---
        if challenge_timeframe == "this month":
            return self._handle_this_month(
                handler_input, challengeData, current_month_key, day, last_day,
                categories, use_imperial, now)

        if challenge_timeframe == "next month":
            return self._handle_next_month(
                handler_input, challengeData, now, categories, use_imperial)

        if challenge_timeframe == "next week":
            # Calculate the date 7 days from now
            next_week = now + timedelta(days=7)
            month_key = next_week.strftime("%Y-%m")
            month_data = challengeData.get(month_key)
            if month_data is None:
                speak = "I don't have next week's challenge schedule yet."
                return handler_input.response_builder.speak(speak).ask(" ").response
            entry, _ = _find_challenge_for_day(month_data, next_week.day)
            if entry is None:
                speak = "I don't have challenge data for next week."
                return handler_input.response_builder.speak(speak).ask(" ").response
            timeframe_label = "Next week"
            answer_date = next_week
        else:
            # Default: this week
            month_data = challengeData.get(current_month_key)
            if month_data is None:
                speak = "I don't have challenge data for this month."
                return handler_input.response_builder.speak(speak).ask(" ").response
            entry, _ = _find_challenge_for_day(month_data, day)
            if entry is None:
                speak = "I don't have challenge data for this week."
                return handler_input.response_builder.speak(speak).ask(" ").response
            timeframe_label = "This week"
            answer_date = now

        # --- Set session context for AfterThat follow-ups ---
        session_attr = handler_input.attributes_manager.session_attributes
        session_attr['last_context'] = 'challenge'
        session_attr['last_challenge_date'] = answer_date.strftime("%Y-%m-%d")
        session_attr['last_challenge_categories'] = categories

        # --- Format response ---
        speak = self._format_response(
            entry, categories, challenge_detail, timeframe_label, use_imperial)

        if _needs_ssml(speak):
            speak = "<speak>" + speak + "</speak>"

        return (
            handler_input.response_builder
                .speak(speak)
                .ask(" ")
                .response
        )

    def _format_response(self, entry, categories, detail, timeframe_label, use_imperial):
        """Build the spoken response for a single week's challenge data."""
        parts = []

        for cat in categories:
            if cat not in entry:
                continue
            ch = entry[cat]
            label = _challenge_type_label(cat)
            name = _format_challenge_name(ch)

            if detail == "XP":
                parts.append("The %s is worth %d experience points." % (label, ch["xp"]))
            elif detail == "distance":
                dist = _format_distance(ch, use_imperial)
                if dist:
                    parts.append("The %s, %s, is %s long." % (label, name, dist))
                else:
                    parts.append("I don't have the distance for %s." % name)
            elif detail == "elevation":
                elev = _format_elevation(ch, use_imperial)
                if elev:
                    parts.append("The %s, %s, has %s of elevation gain." % (label, name, elev))
                else:
                    parts.append("I don't have the elevation for %s." % name)
            else:
                # Overview: name + XP, plus distance/elevation if available
                short_label = _challenge_type_label(cat, short=True)
                overview = "%s's %s is %s, worth %d XP." % (
                    timeframe_label, short_label, name, ch["xp"])
                dist = _format_distance(ch, use_imperial)
                elev = _format_elevation(ch, use_imperial)
                if dist and elev:
                    overview += " It's %s long with %s of elevation gain." % (dist, elev)
                elif dist:
                    overview += " It's %s long." % dist
                elif elev:
                    overview += " It has %s of elevation gain." % elev
                parts.append(overview)

        if not parts:
            return "I don't have challenge data for that."

        return " ".join(parts)

    def _handle_this_month(self, handler_input, data, month_key, day, last_day,
                           categories, use_imperial, now):
        """List remaining challenges for this month."""
        month_data = data.get(month_key)
        if not month_data:
            speak = "I don't have challenge data for this month."
            return handler_input.response_builder.speak(speak).ask(" ").response

        start_days = sorted(int(d) for d in month_data.keys())
        # Filter to entries that are still active (start day + next start covers today or later)
        remaining = []
        for i, start in enumerate(start_days):
            # An entry is "remaining" if its active period overlaps with today or later
            if i + 1 < len(start_days):
                end = start_days[i + 1] - 1
            else:
                end = last_day
            if end >= day:
                remaining.append((start, end, month_data[str(start)]))

        if not remaining:
            speak = "There are no more challenge routes this month."
            return handler_input.response_builder.speak(speak).ask(" ").response

        for cat in categories:
            label = _challenge_type_label(cat, short=True) + "s"
            names = []
            for start, end, entry_data in remaining:
                if cat not in entry_data:
                    continue
                ch = entry_data[cat]
                name = _format_challenge_name(ch)
                start_dt = now.replace(day=start)
                end_dt = now.replace(day=end)
                if start <= day:
                    names.append("%s through %s" % (name, _ordinal_date_string(end_dt)))
                else:
                    names.append("%s starting %s" % (name, _ordinal_date_string(start_dt)))

            if names:
                speak = "The remaining %s this month are: %s." % (label, ", then ".join(names))
                if _needs_ssml(speak):
                    speak = "<speak>" + speak + "</speak>"
                return (
                    handler_input.response_builder
                        .speak(speak)
                        .ask(" ")
                        .response
                )

        speak = "I don't have challenge data for this month."
        return handler_input.response_builder.speak(speak).ask(" ").response

    def _handle_next_month(self, handler_input, data, now, categories, use_imperial):
        """List challenges for next month."""
        if now.month == 12:
            next_month_key = "%04d-01" % (now.year + 1)
        else:
            next_month_key = "%04d-%02d" % (now.year, now.month + 1)

        month_data = data.get(next_month_key)
        if not month_data:
            speak = "I don't have next month's challenge schedule yet."
            return handler_input.response_builder.speak(speak).ask(" ").response

        start_days = sorted(int(d) for d in month_data.keys())

        for cat in categories:
            label = _challenge_type_label(cat, short=True) + "s"
            names = []
            for start in start_days:
                entry_data = month_data[str(start)]
                if cat not in entry_data:
                    continue
                ch = entry_data[cat]
                name = _format_challenge_name(ch)
                names.append("%s starting the %s" % (name, _ordinal_suffix(start)))

            if names:
                speak = "Next month's %s are: %s." % (label, ", then ".join(names))
                if _needs_ssml(speak):
                    speak = "<speak>" + speak + "</speak>"
                return (
                    handler_input.response_builder
                        .speak(speak)
                        .ask(" ")
                        .response
                )

        speak = "I don't have next month's challenge schedule yet."
        return handler_input.response_builder.speak(speak).ask(" ").response


def _ordinal_suffix(day_num):
    """Return day number with ordinal suffix (e.g., '1st', '2nd', '3rd')."""
    if 11 <= day_num <= 13:
        return str(day_num) + "th"
    elif day_num % 10 == 1:
        return str(day_num) + "st"
    elif day_num % 10 == 2:
        return str(day_num) + "nd"
    elif day_num % 10 == 3:
        return str(day_num) + "rd"
    else:
        return str(day_num) + "th"


class ZwiftTimeIntentHandler(AbstractRequestHandler):
    """Handler for Zwift Time Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("ZwiftTimeIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("Handling ZwiftTimeIntent")
        now, day, midnight, last_day = _get_time_state()
        speak_output = "In Eastern time, the day is " + str(day)

        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask("add a reprompt if you want to keep the session open for the user to respond")
                .response
        )


class NextWorldIntentHandler(AbstractRequestHandler):
    """Handler for Next World Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("NextWorldIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("Handling NextWorldIntent")
        error = _data_unavailable_response(handler_input)
        if error:
            return error
        now, day, midnight, last_day = _get_time_state()

        # Determine if the world will change from the current world before the end of the month
        nextDay = day+1
        while ((nextDay <= last_day) and (worldList[nextDay] == worldList[day])):
            nextDay+=1

        if (nextDay > last_day):
            speak_output = "I don't know next month's schedule yet. " + worldList[day] + " are available today."
        elif (worldList[nextDay] == worldList[day]):
            speak_output = worldList[nextDay] + "will be active through the end of this month."
        else:
            speak_output = "The next worlds will be " + worldList[nextDay] + ". They will be available "
            if nextDay - day == 1:
                delta = midnight - now
                speak_output += " in " + str(delta.seconds//3600) + " hours and " + str((delta.seconds//60) % 60) + " minutes."
            elif nextDay-day == 2:
                speak_output += "in two days."
            else:
                speak_output += str(nextDay-day) + " days from now."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(" ")
                .response
        )


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "You can say, what are today's guest worlds? Where can I ride tomorrow? What's available this weekend? What's Next? Or, when can I run in London?"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Goodbye!"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Any cleanup logic goes here.

        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):
    """The intent reflector is used for interaction model testing and debugging.
    It will simply repeat the intent the user said. You can create custom handlers
    for your intents by defining them above, then also adding them to the request
    handler chain below.
    """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output = "You just triggered " + intent_name + "."

        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask("add a reprompt if you want to keep the session open for the user to respond")
                .response
        )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors. If you receive an error
    stating the request handler chain is not found, you have not implemented a handler for
    the intent being invoked or included it in the skill builder below.
    """
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

# The SkillBuilder object acts as the entry point for your skill, routing all request and response
# payloads to the handlers above. Make sure any new handlers or interceptors you've
# defined are included below. The order matters - they're processed top to bottom.


sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(TodaysWorldIntentHandler())
sb.add_request_handler(TomorrowsWorldIntentHandler())
sb.add_request_handler(WhenWorldIntentHandler())
sb.add_request_handler(WorldOnDateIntentHandler())
sb.add_request_handler(AfterThatIntentHandler())
sb.add_request_handler(WeeklyChallengeIntentHandler())
sb.add_request_handler(ZwiftTimeIntentHandler())
sb.add_request_handler(NextWorldIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
