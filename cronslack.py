#! /usr/bin/env python2.7

import optparse

import reminder
import slacker
import token


parser = optparse.OptionParser()
parser.add_option("-s", "--slack", dest="slack", \
    help="Name of Slack (everything before .slack.com)")
parser.add_option("-c", "--config", dest="config", \
    help="Name of Slack channel for config information")
parser.add_option("-l", "--log", dest="log", \
    help="Name of Slack channel for log output")
parser.add_option("-d", "--delete-after", type="int", default=600, dest="delete", \
    help="Number of seconds before we delete outdated config lines")

(options, args) = parser.parse_args()

api_token = token.token()

slacker = slacker.Slacker(options.slack, api_token)

reminder = reminder.Reminder(options.config, options.log, options.delete, slacker)
reminder.loop()
