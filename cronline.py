#! /usr/bin/env python2.7

import datetime
import re

import croniter

class Cronline(object):

    def __init__(self, message):
        now = datetime.datetime.now()
        minuteago = now - datetime.timedelta(minutes=1)
        self.valid = False
        self.text = message['text']
        self.ts = message['ts']
        tokens = self.text.split()
        # is this a 'one-time' timestamp trigger? (HHMM)
        if re.match("^\d\d\d\d$", tokens[0]):
            self.dt = self.convert_timestamp(tokens.pop(0))
            self.destination = tokens.pop(0)
            self.message = " ".join(tokens)
            self.onetime = True
            self.valid = True
        # If not, is this a cron spec?
        cronspec = " ".join(tokens[0:5])
        if croniter.croniter.is_valid(cronspec):
            cron = croniter.croniter(cronspec, minuteago)
            self.dt = cron.get_next(datetime.datetime)
            self.destination = tokens[5]
            self.message = " ".join(tokens[6:])
            self.onetime = False
            self.valid = True

    def convert_timestamp(self, ts):
        """
        Given an HHMM return the next datetime.datetime that will 
        match it.
        If HHMM can be later today (e.g. HHMM is 1013 and now is 0910)
        return datetime.datetime today at 1013; but if now is 1013 and
        HHMM is 0910, return tomorrow's 0910
        """
        now = datetime.datetime.now()
        hour = int(ts[0:2])
        minute = int(ts[2:4])
        spec = datetime.datetime(now.year, now.month, now.day, hour, minute)
        if self.same_time(spec, now) or spec > now:
            return spec
        spec += datetime.timedelta(days=1)
        return spec

    def execute_now(self):
        """
        Should we execute this crontab at this minute?
        """
        now = datetime.datetime.now()
        return self.same_time(now)

    def same_time(self, dt, dt2=None):
        """
        returns True if my dt and the given dt are identical to the minute
        """
        if not dt2:
            dt2 = self.dt
        if dt2.year != dt.year:
            return False
        if dt2.month != dt.month:
            return False
        if dt2.day != dt.day:
            return False
        if dt2.hour != dt.hour:
            return False
        if dt2.minute != dt.minute:
            return False
        return True

