# -*- coding: utf-8 -*-

# This sample demonstrates handling intents from an Alexa skill using the Alexa Skills Kit SDK for Python.
# Please visit https://alexa.design/cookbook for additional examples on implementing slots, dialog management,
# session persistence, api calls, and more.
# This sample is built using the handler classes approach in skill builder.
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
    now = datetime.now(tz.gettz('America/Halifax'))
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

        return (
            handler_input.response_builder
                .speak(speak_output)
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

        if day < last_day:
            speak_output = "Tomorrow's Guest Worlds are " + worldList[day + 1]
        else:
            speak_output = "I don't know next month's schedule yet. " + worldList[day] + " are available today. Ask me again tomorrow."

        return (
            handler_input.response_builder
                .speak(speak_output)
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


        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask("add a reprompt if you want to keep the session open for the user to respond")
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
            return handler_input.response_builder.speak(speak).response
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
            return handler_input.response_builder.speak(speak).response

        # Filter to only future/today dates
        dates = future

        if len(dates) == 1:
            # Single date
            d, dt = dates[0]
            speak = "On " + _ordinal_date_string(dt) + ", the guest worlds will be " + worldList[d] + "."
            return handler_input.response_builder.speak(speak).response

        # Weekend (2 dates)
        d1, dt1 = dates[0]
        d2, dt2 = dates[1]

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
            return handler_input.response_builder.speak(speak).response
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
            return handler_input.response_builder.speak(speak).response


class ZwiftTimeIntentHandler(AbstractRequestHandler):
    """Handler for Zwift Time Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("ZwiftTimeIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("Handling ZwiftTimeIntent")
        now, day, midnight, last_day = _get_time_state()
        speak_output = "In Halifax, the day is " + str(day)

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
sb.add_request_handler(ZwiftTimeIntentHandler())
sb.add_request_handler(NextWorldIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
