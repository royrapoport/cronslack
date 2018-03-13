#! /usr/bin/env python2.7

import json
import time

import requests


class Slacker(object):

    def __init__(self, slack, token):

        self.slack = slack
        self.token = token

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

