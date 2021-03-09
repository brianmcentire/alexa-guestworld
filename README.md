# alexa-guestworld
An Alexa Skill for getting information about which Guest Worlds are live and coming up in Zwift

Zwift is a massively multiplayer online game which brings cyclists and athletes from all over the world together in a virtual world to race or train together. It also provides an immersive environment for individuals to train in to take the boredom out of riding indoors.

The platform offers a choice of worlds to ride and run in, which changes from day to day. When starting a session, users have a choice of one of 3 active worlds. There are several websites which offer current and upcoming world information:
  * https://whatsonzwift.com/
  * https://community.zwift.com/ (Guest World Schedule, although not all worlds are represented in the color coded key)
  
This Alexa Guest World Calendar skill provides another method, it is the one I prefer to use to inquire about my upcoming ride options while having morning coffee.

This skill is invoked with "Alexa, ask Which World..." 

Some of the questions (intents) this skill will answer are:
  * "Where can I ride today?"
  * "When can I run in London?"
  * "What guest world is next?"
  
I developed this code to "scratch an itch" and decided to share it with Zwifters all over the world. It is available for free and is published in the Alexa Store:
  * https://www.amazon.com/B-Scott-Guest-World-Calendar/dp/B084ZVL2Y8/ref=sr_1_1?dchild=1&keywords=guest+world+calendar&qid=1615303648&s=digital-skills&sr=1-1#customerReviews
  
This skill has users from all corners of the world. I hope you enjoy it too!

### Upcoming features
Currently, calendar data must be updated manually at the begginning of each month. Data is pulled from the Zwift community website, transformed, and then uploaded to S3 for access by this skill. Pulling data directly from Zwift's API would eliminate the need for manual updates.
