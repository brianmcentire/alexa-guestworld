# -*- coding: utf-8 -*-

# This sample demonstrates handling intents from an Alexa skill using the Alexa Skills Kit SDK for Python.
# Please visit https://alexa.design/cookbook for additional examples on implementing slots, dialog management,
# session persistence, api calls, and more.
# This sample is built using the handler classes approach in skill builder.
import logging
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


class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Welcome, you can say. What are todays guest worlds? Where can I ride tomorrow? What's Next? Or, when can I run in London?"

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

        speak_output = "Todays Guest Worlds are " + worldList[dayNumber]

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
        if (dayNumber + 1 < lastDayOfMonth):
            speak_output = "Tomorrow's Guest Worlds are " + worldList[dayNumber + 1]
        else:
            speak_output = "I don't know next month's schedule yet. " + worldList[dayNumber] + " are available today. Ask me again tomorrow."
        
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
        
        ## This worked but returned wotopia rather than Watopia
        ## worldName = handler_input.request_envelope.request.intent.slots['WorldName'].value
        worldName = handler_input.request_envelope.request.intent.slots['GuestWorldName'].resolutions.resolutions_per_authority[0].values[0].value.name
        
        
        if worldName == "Watopia":
            speak_output = "Watopia is available today and every day."
        else:
            speak_output = "  "
            ##DEBUG
            ##speak_output = "you asked about " + worldName.value + ". "
            
            lookupDay = day
            # Be sure to compare case insensitive and eliminate white space spaces because of data source words like NEWYORK vs New York
            worldNameToMatch = worldName.casefold().replace(" ","")
            while True:
                if lookupDay > lastDayOfMonth:
                    break
                if worldNameToMatch in worldList[lookupDay].casefold().replace(" ",""):
                    break
                lookupDay += 1
            
            speak_output += worldName
            if (lookupDay == day):
                speak_output += " is available now."
            elif lookupDay > lastDayOfMonth:
                speak_output += " won't be available until sometime next month."
            elif (lookupDay - day) == 1:
                speak_output += " will be available tomorrow."
            else:
                speak_output += " will be available " + str(lookupDay - day) + " days from now."


        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask("add a reprompt if you want to keep the session open for the user to respond")
                .response
        )


class ZwiftTimeIntentHandler(AbstractRequestHandler):
    """Handler for Zwift Time Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("ZwiftTimeIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "In Halifax, the day is " + str(dayNumber)

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

        # Determine if the world will change from the current world before the end of the month
        nextDay = day+1
        while ((nextDay <= lastDayOfMonth) and (worldList[nextDay] == worldList[day])):
            nextDay+=1

        if (nextDay > lastDayOfMonth):
            speak_output = "I don't know next month's schedule yet. " + worldList[dayNumber] + " are available today."
        elif (worldList[nextDay] == worldList[day]):
            speak_output = worldList[nextDay] + "will be active through the end of this month."
        else:
            speak_output = "The next worlds will be " + worldList[nextDay] + ". They will be available "
            ## still need to handle "later today ie in 5 hours" or could handle all by X hours from now just watch timezone
            ## Yeah, this will say 3 days when really its just two days plus an hour away and it shouldn't do that
            if nextDay - day == 1:
                ##speak_output += "tomorrow."
                delta = midnightInHalifax - nowInHalifax
                speak_output += " in " + str(delta.seconds//3600) + " hours and " + str((delta.seconds//60) % 60) + " minutes." 
                ##speak_output += str(handler_input.request_envelope.session.user)
                ##speak_output += str(handler_input.request_envelope.context)
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
        speak_output = "You can say, what are today's guest worlds? Where can I ride tomorrow? What's Next? Or, when can I run in London?"

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

# Keep in mind the guest course changeover happens at 20:00 Los Angeles time (PST) or UTC-8 hrs == midnight UTC-4 ie Halifax.
nowInHalifax = datetime.now(tz.gettz('America/Halifax'))
dayNumber = nowInHalifax.day
midnightInHalifax = datetime.replace(nowInHalifax + timedelta(days=1),hour=0,minute=0,second=0)

# Read the processed calendar from S3 into a list/array for quick and easy lookups
# get a handle on s3
s3 = boto3.resource('s3')

# S3 bucket to query (Change this to your bucket)
S3_BUCKET = 'guestworldskill'
Key='GuestWorlds.csv'

# get a handle on the bucket that holds your file
bucket = s3.Bucket(S3_BUCKET)

# get a handle on the object you want (i.e. your file)
obj = bucket.Object(Key)

# get the object
response = obj.get()

# Determine current day and last day of month for bounds checking
day = nowInHalifax.day
## There could be some edge cases next line when Halifax is on the 1st but local time is still on last day of month
lastDayOfMonth = calendar.monthrange(datetime.now().year,datetime.now().month)[1]

# Initialize array with a value at zero so array can by indexed by day
worldList = ["IndexZero"]

# Read in the s3 object, lines is a list of each line delineated by newline
# python 3 syntax needed to decode the incoming bytes successfully:
lines = response['Body'].read().decode('utf-8').split('\n')

# Build up  worldList (by appending the worlds as they are read in day by day)
# CSV file on S3 is format "WORLD, Day" so split by the comma and keep first
for row in lines:
    row = row.split(",")
    #Fix NEWYORK to be added as New York with string replacement at time of building worldList array 
    worldList.append(row[0].replace("NEWYORK","New York"))

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(TodaysWorldIntentHandler())
sb.add_request_handler(TomorrowsWorldIntentHandler())
sb.add_request_handler(WhenWorldIntentHandler())
sb.add_request_handler(ZwiftTimeIntentHandler())
sb.add_request_handler(NextWorldIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()