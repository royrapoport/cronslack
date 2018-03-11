#! /usr/bin/env python2.7

import datetime
import json
import optparse
import os
import re
import time

import requests

import cronline
import token


class Reminder(object):

    def __init__(self, slack, config, log, delete):

        self.slack = slack
        self.config_channel_name = config
        self.log_channel_name = log
        self.delete_done_after = delete
        self.token = token.token()
        assert self.token
        self.cache_ids()
        self.config_channel_id = self.get_channel_id(self.config_channel_name)
        self.log_channel_id = self.get_channel_id(self.log_channel_name)
        self.log("Reminder.__init__ completed")
        self.loop()

    def log(self, message):
        # print "Logging '{}'".format(message)
        self.channel_post(message, self.log_channel_id, link_names=False)

    def user_post(self, message, id):
        # annoyingly, we first need to create a DM channel, then get its ID, then do the needful
        # print "Trying to create IM channel to {}".format(id)
        payload = self.api_call("im.open?user={}".format(id), requests.post)
        # print json.dumps(payload)
        channel_id = payload['channel']['id']
        self.channel_post(message, channel_id)

    def channel_post(self, message, channel_id, link_names=True, ts=None):
        """
        posts a message; unless ts is given, in which case we'll *update* the message with the given
        ts instead
        """
        post = {'channel': channel_id, 'text': message, 'as_user': True, 'link_names': True}
        method = "chat.postMessage"
        if ts:
            post['ts'] = ts
            method = "chat.update"
        self.api_call(method, method=requests.post, json=post, header_for_token=True)

    def execute(self, cline):
        id = self.find_id(cline.destination)
        if not id:
            self.log("Could not find ID for {}".format(destination))
            return
        if '#' in cline.destination:
            self.channel_post(cline.message, id)
        else:
            self.user_post(cline.message, id)
        if cline.onetime:
            self.update_message(cline.text, cline.ts)

    def update_message(self, message, ts):
         now_friendly = time.ctime()
         now_computer = time.time()
         new_text = "EXECUTED on {} {}: \n{}".format(now_computer, now_friendly, message)
         self.channel_post(new_text, self.config_channel_id, ts=ts)

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

    def loop(self):
        now = datetime.datetime.now()
        while True:
            cronlines = self.get_cronlines()
            for cline in cronlines:
                execute = False
                if cline.execute_now():
                    self.execute(cline)
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
        self.api_call("chat.delete?ts={}&channel={}".format(ts, self.config_channel_id))

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
        payload = self.api_call(api)
        return [message for message in payload["messages"] if message.get("subtype") is None]

    def cache_ids(self):
        """
        cache name:id mapping for channels, groups, and users
        """
        self.cache = {}
        self.cache['groups'] = {}
        private_groups = self.paginated_lister("groups.list", "groups")
        self.cache['groups'] = {group['name_normalized']: group['id'] for group in private_groups}
        channels = self.paginated_lister("channels.list?exclude_members=true", 'channels')
        self.cache['channels'] = {channel['name_normalized']: channel['id'] for channel in channels}
        users = self.paginated_lister("users.list?presence=false", 'members')
        self.cache['users'] = {user['name']: user['id'] for user in users}

    def paginated_lister(self, api_call, element_name, limit=200):

        start = time.time()
        done = False
        cursor = None
        results = []
        separator = self.use_separator(api_call)
        api_call = api_call + separator + "limit={}".format(limit)
        while not done:
            interim_api_call = api_call
            if cursor:
                interim_api_call += "&cursor={}".format(cursor)
            interim_results = self.api_call(interim_api_call)
            results += interim_results[element_name]
            cursor = interim_results.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                done = True
        end = time.time()
        diff = end - start
        print "Loaded {} {} in {:.1f} seconds".format(len(results), element_name, diff)
        return results


    def get_channel_id(self, channel_name):
        if channel_name in self.cache['groups']:
            self.message_api = "groups.history"
            return self.cache['groups'][channel_name]
        elif channel_name in self.cache['channels']:
            self.message_api = "channels.history"
            return self.cache['channels'][channel_name]
        else:
            raise RuntimeError("Could not find an ID for channel {}".format(channel_name))

    def use_separator(self, url):
        """
        if url already has '?', use &; otherwise, use '?'
        """
        separator = "?"
        if '?' in url:
            separator = "&"
        return separator

    def api_call(self, api_endpoint, method=requests.get, json=None, header_for_token=False):
        url = "https://{}.slack.com/api/{}".format(self.slack, api_endpoint)
        headers = {}
        if header_for_token:
            headers['Authorization'] = "Bearer {}".format(self.token)
        else:
            separator = self.use_separator(url)
            url += "{}token={}".format(separator, self.token)
        if json:
            headers['Content-Type'] = "application/json"
        # print "url: {}".format(url)
        done = False
        while not done:
            response = method(url, json=json, headers=headers)
            if response.status_code == 200:
                done = True
            if response.status_code == 429:
                retry_after = int(response['Retry-After']) + 1
                time.sleep(retry_after)
        payload = response.json()
        # print "json: {} headers: {}".format(json, headers)
        # print "status code: {} payload: {}".format(response.status_code, payload)
        return payload


if __name__ == "__main__":

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

    reminder = Reminder(options.slack, options.config, options.log, options.delete)
    reminder.loop()
