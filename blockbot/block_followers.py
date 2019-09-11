'''
    block_followers
    ===============

    Block followers of a certain accounts, by screen-name.

    Block followers **does** not block an account if the account is
    whitelisted. See [whitelist.py](whitelist.py) for more information.

    # Warnings

    The rate-limiting factor is the number of API calls, which increases
    exponentially with the number of whitelisted users. A memo is provided
    to avoid repeatedly querying seen users, which also allows you to
    continue an interrupted query with minimal overhead. Only whitelist
    a small number of users.

    # Sample Use

    .. code-block:: python

        import blockbot

        accounts = ['twitter']
        whitelist = ['jack']
        blockbot.block_followers(accounts, whitelist)
'''

import tweepy

from . import api
from . import collections
from . import log
from . import whitelist

# Previously seen account screen names.
ACCOUNTS_SEEN = collections.wired_tiger_set('BlockFollowersAccountsSeen')
# Previously blocked account screen names.
ACCOUNTS_BLOCKED = collections.wired_tiger_set('BlockFollowersAccountsBlocked')


def followers(api, screen_name):
    '''Get user objects for all followers of an account.'''

    log.info(f'Getting followers for {screen_name}.')
    try:
        for user in tweepy.Cursor(api.followers, screen_name=screen_name).items():
            yield user
    except tweepy.TweepError:
        log.warn(f'Unable to get followers for account {screen_name}')


def block_account(api, me, user, whiteset, **kwds):
    '''Block account if not white-listed.'''

    if user.screen_name in ACCOUNTS_SEEN:
        return

    ACCOUNTS_SEEN.add(user.screen_name)
    if whitelist.should_block_user(api, me, user, whiteset, **kwds):
        ACCOUNTS_BLOCKED.add(user.screen_name)
        log.info(f'Blocked user={user.screen_name}')
        if not getattr(user, 'blocking', False):
            api.create_block(screen_name=user.screen_name)


def block_followers(accounts, whitelist=None, **kwds):
    '''
    Block all followers of a given account, except whitelisted accounts.

    :param accounts: Iterable of screen names to block followers of those accounts.
    :param whitelist: (Optional) Optional iterable of screen names to whitelist.
    :param **kwds: Optional keyword-arguments to override account whitelisting.
    '''

    tweepy_api = api.generate_api()
    me = tweepy_api.me()
    whiteset = set(whitelist or [])
    for account in accounts:
        for follower in followers(tweepy_api, account):
            block_account(tweepy_api, me, follower, whiteset, **kwds)
