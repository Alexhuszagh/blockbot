'''
    api
    ===

    High-level utility to access the Twitter API.

    Update config/api.json to update credentials.
'''

import json
import os
import tweepy

from . import path


def generate_api():
    '''Generate the API from config.'''

    with open(os.path.join(path.config_dir(), 'api.json')) as f:
        api_data = json.load(f)

    consumer_key = api_data['consumer_key']
    consumer_secret = api_data['consumer_secret']
    access_token = api_data['access_token']
    access_token_secret = api_data['access_token_secret']
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    return tweepy.API(
        auth,
        wait_on_rate_limit=True,
        wait_on_rate_limit_notify=True,
        compression=True
    )
