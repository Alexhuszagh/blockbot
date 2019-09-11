'''
    block_followers
    ===============

    Block followers of a certain accounts, by screen-name.

    Reads configuration settings from `config/block_followers.json`.
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

    with open(os.path.join(config_dir(), 'block_followers.json')) as f:
        config = json.load(f)
        if not config['accounts']:
            raise ValueError('Must provide at least one account to block followers from.')
    return config


def main():
    config = load_config()
    blockbot.as_daemon(
        blockbot.block_followers,
        accounts=config['accounts'],
        whitelist=config['whitelist'],
        **config['keywords'],
    )


if __name__ == '__main__':
    main()

