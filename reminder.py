#! /usr/bin/env python2.7

import datetime
import re
import time

import cronline
import slacker
import token


class Reminder(object):

    def __init__(self, config, log, delete, slacker):

        self.slacker = slacker
        self.config_channel_name = config
        self.log_channel_name = log
        self.delete_done_after = delete
        self.cache_ids()
        self.config_channel_id = self.get_channel_id(self.config_channel_name)
        self.log_channel_id = self.get_channel_id(self.log_channel_name)
        self.log("Reminder.__init__ completed")
        self.loop()

    def log(self, message):
        self.slacker.channel_post(message, self.log_channel_id, link_names=False)

    def execute(self, cline):
        id = self.find_id(cline.destination)
        if not id:
            self.log("Could not find ID for {}".format(destination))
            return
        if '#' in cline.destination:
            self.slacker.channel_post(cline.message, id)
        else:
            self.slacker.user_post(cline.message, id)
        if cline.onetime:
            self.update_message(cline.text, cline.ts)

    def update_message(self, message, ts):
         now_friendly = time.ctime()
         now_computer = time.time()
         new_text = "EXECUTED on {} {}: \n{}".format(now_computer, now_friendly, message)
         self.slacker.channel_post(new_text, self.config_channel_id, ts=ts)

    def find_id(self, destination):
        # print "Finding id in {}".format(destination)
        if re.match("<#.+\|.+>", destination):
            id, name = destination.split("|")
            return id[2:]
        if re.match("<@.*>", destination):
            return destination[2:-1]
        subdestination = destination[1:]
        self.log("Trying to find ID for {}".format(subdestination))
        if destination[0] == '@':
            return self.cache['members'].get(subdestination)
        if destination[0] == '#':
            if subdestination in self.cache['channels']:
                return self.cache['channels'][subdestination]
            elif subdestination in self.cache['groups']:
                return self.cache['groups'][subdestination]
        return None

    def execute_once(self):
        cronlines = self.get_cronlines()
        for cline in cronlines:
            execute = False
            if cline.execute_now():
                self.execute(cline)

    def loop(self):
        now = datetime.datetime.now()
        while True:
            self.execute_once()
            later = datetime.datetime.now()
            diff = later - now
            seconds = diff.seconds
            # self.log("Executed in {} seconds".format(seconds))
            if later.minute == now.minute:
                sleep_for = 60 - later.second
                # self.log("Will sleep for {} seconds".format(sleep_for))
                time.sleep(sleep_for)
            now = datetime.datetime.now()

    def potential_delete(self, message):
        """
        figure out when we executed and, if delete_done_after is set
        delete the message it's been at least that many seconds
        """
        if not self.delete_done_after:
            return
        text = message['text']
        ts = message['ts']
        done = re.sub("EXECUTED on (\d+).*", r"\1", text, re.M)
        # that keeps the next line in done, and I'm too tired to figure out how to much
        # with re to have it do the multiline match, so just split and discard
        done = done.split()[0]
        done = int(done)
        now = time.time()
        diff = now - done
        if diff > self.delete_done_after:
            m = "Deleted config message '{}' because it was too old".format(text)
            self.log(m)
            self.delete_config_message(ts)

    def delete_config_message(self, ts):
        self.slacker.api_call("chat.delete?ts={}&channel={}".format(ts, self.config_channel_id))

    def get_cronlines(self):
        """
        returns a list of cronlines; each cronline is a 
        [datetime_to_next execution, destination, message, ts, onetime]
        spec
        (onetime is binary)
        """
        messages = self.get_messages()
        cronlines = []
        for message in messages:
            cline = cronline.Cronline(message)
            if cline.valid:
                cronlines.append(cline)
                continue
            # if we got here, the cline is not valid
            if message['text'].find("EXECUTED on") == 0:
                self.potential_delete(message)
            else:
                self.log("Skipping message {} because it's neither HHMM or cron".format(message))
                continue
        # print "cronlines: {}".format(cronlines)
        return cronlines

    def get_messages(self):
        api = self.message_api + "?channel={}".format(self.config_channel_id)
        payload = self.slacker.api_call(api)
        return [message for message in payload["messages"] if message.get("subtype") is None]

    def cache_ids(self):
        """
        cache name:id mapping for channels, groups, and users
        """
        self.cache = {}
        self.cache['groups'] = {}
        private_groups = self.slacker.paginated_lister("groups.list", "groups")
        self.cache['groups'] = {group['name_normalized']: group['id'] for group in private_groups}
        channels = self.slacker.paginated_lister("channels.list?exclude_members=true", 'channels')
        self.cache['channels'] = {channel['name_normalized']: channel['id'] for channel in channels}
        users = self.slacker.paginated_lister("users.list?presence=false", 'members')
        self.cache['users'] = {user['name']: user['id'] for user in users}

    def get_channel_id(self, channel_name):
        if channel_name in self.cache['groups']:
            self.message_api = "groups.history"
            return self.cache['groups'][channel_name]
        elif channel_name in self.cache['channels']:
            self.message_api = "channels.history"
            return self.cache['channels'][channel_name]
        else:
            raise RuntimeError("Could not find an ID for channel {}".format(channel_name))
