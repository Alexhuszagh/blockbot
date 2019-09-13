#!/usr/bin/env python3
'''
    block_media_replies
    ===================

    Block all accounts that reply to an account with media in their reply.

    Reads configuration settings from `config/block_media_replies.json`.
'''

import json
import os

try:
    import blockbot
except ImportError:
    # Script probably not installed, in scripts directory.
    import sys
    project_home = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    sys.path.insert(0, project_home)
    import blockbot

from blockbot.path import config_dir


def load_config():
    '''Read configuration file.'''

    with open(os.path.join(config_dir(), 'block_media_replies.json')) as f:
        config = json.load(f)
        if not config['account_screen_name']:
            raise ValueError('Must provide screen name for account replied to.')
    return config


def main():
    config = load_config()
    blockbot.as_daemon(
        blockbot.block_media_replies,
        account_screen_name=config['account_screen_name'],
        whitelist_screen_names=config['whitelist_screen_names'],
        **config['keywords'],
    )


if __name__ == '__main__':
    main()
