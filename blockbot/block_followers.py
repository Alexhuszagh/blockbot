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

        account_screen_names = ['twitter']
        whitelist_screen_names = ['jack']
        blockbot.block_followers(account_screen_names, whitelist_screen_names)
'''

import tweepy

from . import api
from . import collections
from . import log
from . import whitelist

# Logger for BlockFollowers.
LOGGER = log.new_logger('BlockFollowers')
# Previously processed accounts.
ACCOUNTS_PROCESSED = collections.wired_tiger_dict(
    name='BlockFollowersProcessedAccounts',
    key_format='r',
    value_format='Sr',
    columns=('user_id', 'screen_name', 'cursor')
)
# Previously seen account screen names.
FOLLOWERS_SEEN = collections.wired_tiger_dict(
    name='BlockFollowersSeenFollowers',
    key_format='r',
    value_format='S',
    columns=('user_id', 'screen_name')
)
# Previously blocked account screen names.
FOLLOWERS_BLOCKED = collections.wired_tiger_dict(
    name='BlockFollowersBlockedFollowers',
    key_format='r',
    value_format='SbbbbQQQQQSSSSSSSrS',
    columns=(
        # Basic Follower Info
        'follower_id',
        'follower_screen_name',
        # Booleans.
        'follower_default_profile',
        'follower_default_profile_image',
        'follower_protected',
        'follower_verified',
        # Numbers.
        'follower_favourites_count',
        'follower_followers_count',
        'follower_friends_count',
        'follower_listed_count',
        'follower_statuses_count',
        # Strings
        'follower_created_at',
        'follower_description',
        'follower_location',
        'follower_name',
        'follower_url',
        'follower_withheld_in_countries',
        'follower_withheld_scope',
        # Basic Account Info
        'account_id',
        'account_screen_name',
    )
)

def followers(tweepy_api, account):
    '''Get user objects for all followers of account.'''

    # Get the current cursor for the account.
    cursor_state = api.CursorState()
    if account.id in ACCOUNTS_PROCESSED:
        cursor_state.next_cursor = ACCOUNTS_PROCESSED[account.id][1]
    if cursor_state.next_cursor == api.END_CURSOR:
        # Previously finished the account, don't make any API requests.
        return

    try:
        count = 0
        for follower in api.followers(
            tweepy_api,
            user_id=account.id,
            cursor_state=cursor_state,
            logger=LOGGER,
        ):
            count += 1
            if count % 50 == 0 and count > 0:
                LOGGER.info(f'Processed {count} followers.')
            yield follower
    except tweepy.TweepError:
        # Store the cursor state on an error and re-raise.
        ACCOUNTS_PROCESSED[account.id] = (account.screen_name, cursor_state.next_cursor)
        raise

    # Store that all followers have been processed for account.
    ACCOUNTS_PROCESSED[account.id] = (account.screen_name, api.END_CURSOR)


def block_follower(tweepy_api, me, account, follower, whitelist_users, **kwds):
    '''Block account if not white-listed.'''

    # Allow repeated requests without incurring API limits.
    if follower.id in FOLLOWERS_SEEN:
        return

    if whitelist.should_block_user(tweepy_api, me, follower, whitelist_users, **kwds):
        if not getattr(follower, 'blocking', False):
            tweepy_api.create_block(user_id=follower.id)

        # Memoize blocked account.
        LOGGER.info(f'Blocked follower={follower.screen_name}')
        FOLLOWERS_BLOCKED[follower.id] = (
            # Basic Follower Info
            follower.screen_name,
            # Booleans
            follower.default_profile,
            follower.default_profile_image,
            follower.protected,
            follower.verified,
            # Numbers
            follower.favourites_count,
            follower.followers_count,
            follower.friends_count,
            follower.listed_count,
            follower.statuses_count,
            # Strings
            str(follower.created_at),
            follower.description or '',
            follower.location or '',
            follower.name,
            follower.url or '',
            ','.join(getattr(follower, 'withheld_in_countries', [])),
            getattr(follower, 'withheld_scope', ''),
            # Basic Account Info
            account.id,
            account.screen_name,
        )

    # Memoize seen account.
    FOLLOWERS_SEEN[follower.id] = follower.screen_name


def block_followers(
    account_screen_names,
    whitelist_screen_names=None,
    account_page_state=None,
    **kwds
):
    '''
    Block all followers of a given account, except whitelisted accounts.

    :param account_screen_names:
        Iterable of screen names to block followers of those accounts.
    :param whitelist_screen_names:
        (Optional) Optional iterable of screen names to whitelist.
    :param account_page_state:
        (Optional) Optional current page state of the account screen names.
    :param **kwds:
        Optional keyword-arguments to override account whitelisting.

    .. code-block:: python

        account_screen_names = ['twitter']
        whitelist_screen_names = ['jack']
        block_followers(account_screen_names, whitelist_screen_names)
    '''

    timeout = kwds.pop('timeout', api.DEFAULT_TIMEOUT)
    tweepy_api = api.generate_api(timeout)
    me = tweepy_api.me()
    accounts = api.lookup_users(
        tweepy_api,
        screen_names=account_screen_names,
        page_state=account_page_state,
        logger=LOGGER,
    )
    whitelist = []
    if whitelist_screen_names is not None:
        whitelist = list(api.lookup_users(
            tweepy_api,
            screen_names=whitelist_screen_names,
            logger=LOGGER,
        ))

    for account in accounts:
        for follower in followers(tweepy_api, account):
            block_follower(tweepy_api, me, account, follower, whitelist, **kwds)
