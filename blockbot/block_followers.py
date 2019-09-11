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

# Logger for BlockFollowers.
LOGGER = log.new_logger('BlockFollowers')
# Previously processed account screen names.
ACCOUNTS_PROCESSED = collections.wired_tiger_dict(
    name='BlockFollowersProcessedAccounts',
    value_format='r'    # cursor
)
# Previously seen account screen names.
FOLLOWERS_SEEN = collections.wired_tiger_set(
    name='BlockFollowersSeenFollowers'
)
# Previously blocked account screen names.
FOLLOWERS_BLOCKED = collections.wired_tiger_dict(
    name='BlockFollowersBlockedFollowers',
    key_format='S',         # screen name
    value_format='S',       # offending account followed
)

def followers(api, screen_name):
    '''Get user objects for all followers of an account.'''

    # Get the current cursor.
    # Can be an integer or None.
    cursor = ACCOUNTS_PROCESSED.get(screen_name)
    if cursor == 0:
        # Previously finished the account, don't make any API requests.
        return

    LOGGER.info(f'Getting followers for {screen_name}.')
    try:
        curr = tweepy.Cursor(
            api.followers,
            screen_name=screen_name,
            cursor=cursor
        )
        for page in curr.pages():
            yield from page
            ACCOUNTS_PROCESSED[screen_name] = curr.iterator.next_cursor
    except tweepy.TweepError:
        LOGGER.warn(f'Unable to get followers for account {screen_name}')

    # Store that all followers have been processed for account.
    ACCOUNTS_PROCESSED[screen_name] = 0


def block_follower(api, me, account, follower, whiteset, **kwds):
    '''Block account if not white-listed.'''

    # Allow repeated requests without incurring API limits.
    if follower.screen_name in FOLLOWERS_SEEN:
        return

    if whitelist.should_block_user(api, me, follower, whiteset, **kwds):
        if not getattr(follower, 'blocking', False):
            api.create_block(screen_name=follower.screen_name)

        # Memoize blocked account.
        LOGGER.info(f'Blocked follower={follower.screen_name}')
        FOLLOWERS_BLOCKED[follower.screen_name] = account

    # Memoize seen account.
    FOLLOWERS_SEEN.add(follower.screen_name)


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
            block_follower(tweepy_api, me, account, follower, whiteset, **kwds)
