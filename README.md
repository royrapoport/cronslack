# cronslack
Use Slack to schedule Slack messages to be sent on Slack later.  #slack.

## Introduction
I had a desire to be able to scheudle Slack messages to be sent at a certain time, mostly to encourage people I work with to have better work/life balance.  For a long time I used /remind for this, but /remind suffers from several flaws for this purpose:

* It looks like a nag
* It looks like an action item
* If you /remind a channel, the channel gets notification *when* you set up the /remind of the /remind.

## How it works

While cronslack is running, once a minute it reads the last 100 messages in a 'config' channel for messages that looked like a spec for when, where, and what to send.  It then sees if that message should be triggered right now, and if so, sends the message to the appropriate destination.  

Message specs are either of the form
`HHMM DESTINATION some text`
or
`CRONSPEC DESTINATION some text`

If HHMM is used, the message will only be sent once; if CRONSPEC, we'll abide by the CRONSPEC; for example, if you say
`*/5 * * * * @royrapoport Hi, this is your 5 minute message!`

Then @royrapoport will get "Hi, this is your 5 minute message!" every 5 minutes.  Perpetually.  And be annoyed.

## How to use 

* Clone this repo.
* Fetch a legacy API token for your Slack.  By default, cronslack looks for an environmental variable called SLACK_API_TOKEN to find this token.  If you want to get it some other way, modify token.py appropriately.

* Run 
> ./cronslack.py -s SLACKNAME -c CONFIGCHANNEL -l LOGCHANNEL [-d SECONDSTODELETION]

`-s is the name of your Slack (everything before '.slack.com')`\
`-c is the name of the channel where config for this should be.  Keep in mind we're not checking who sent the message, so you might want to make this a private channel just for your use`\
`-l is a write-only log channel for actions we took`\
`-d if present is the number of seconds after we ran an HHMM scheduled line before we delete it from the CONFIGCHANNEL`

## Warning

At the time of writing this README.md, I had worked on this for about 8 hours, startting on a Friday afternoon, while dealing with a 4 month old baby.  **On a good day, this code base will barely work.**
