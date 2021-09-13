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
ACCOUNTS_PROCESSED = collections.sqlite_dict(
    table='block_followers_processed_accounts',
    columns=(
        ('user_id', 'TEXT', False),
        ('screen_name', 'TEXT', False),
        ('cursor', 'TEXT', True),
    ),
    primary_key='user_id',
)
# Previously seen account screen names.
FOLLOWERS_SEEN = collections.sqlite_dict(
    table='block_followers_seen_followers',
    columns=(
        ('user_id', 'TEXT', False),
        ('screen_name', 'TEXT', False),
    ),
    primary_key='user_id',
)
# Previously blocked account screen names.
FOLLOWERS_BLOCKED = collections.sqlite_dict(
    table='block_followers_blocked_followers',
    columns=(
        # Basic Follower Info
        ('follower_id', 'TEXT', False),
        ('follower_screen_name', 'TEXT', False),
        # Booleans.
        ('follower_default_profile', 'INTEGER', False),
        ('follower_default_profile_image', 'INTEGER', False),
        ('follower_protected', 'INTEGER', False),
        ('follower_verified', 'INTEGER', False),
        # Numbers.
        ('follower_favourites_count', 'INTEGER', False),
        ('follower_followers_count', 'INTEGER', False),
        ('follower_friends_count', 'INTEGER', False),
        ('follower_listed_count', 'INTEGER', False),
        ('follower_statuses_count', 'INTEGER', False),
        # Strings
        ('follower_created_at', 'TEXT', False),
        ('follower_description', 'TEXT', False),
        ('follower_location', 'TEXT', False),
        ('follower_name', 'TEXT', False),
        ('follower_url', 'TEXT', False),
        ('follower_withheld_in_countries', 'TEXT', False),
        ('follower_withheld_scope', 'TEXT', False),
        # Basic Account Info
        ('account_id', 'TEXT', False),
        ('account_screen_name', 'TEXT', False),
    ),
    primary_key='follower_id',
)

def followers(tweepy_api, account):
    '''Get user objects for all followers of account.'''

    # Get the current cursor for the account.
    cursor_state = api.CursorState()
    previous = ACCOUNTS_PROCESSED.get(str(account.id))
    if previous is not None:
        cursor_state.next_cursor = int(previous['cursor'])
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
        ACCOUNTS_PROCESSED[str(account.id)] = {
            'screen_name': account.screen_name,
            'cursor': str(cursor_state.next_cursor),
        }
        raise

    # Store that all followers have been processed for account.
    ACCOUNTS_PROCESSED[str(account.id)] = {
        'screen_name': account.screen_name,
        'cursor': str(api.END_CURSOR),
    }


def block_follower(tweepy_api, me, account, follower, whitelist_users, **kwds):
    '''Block account if not white-listed.'''

    # Allow repeated requests without incurring API limits.
    if str(follower.id) in FOLLOWERS_SEEN:
        LOGGER.info(f'Already blocked follower={follower.screen_name}')
        return

    if whitelist.should_block_user(tweepy_api, me, follower, whitelist_users, **kwds):
        if not getattr(follower, 'blocking', False):
            api.create_block(tweepy_api, follower.id)

        # Memoize blocked account.
        LOGGER.info(f'Blocked follower={follower.screen_name}')
        withheld_countries = ','.join(getattr(follower, 'withheld_in_countries', []))
        FOLLOWERS_BLOCKED[str(follower.id)] = {
            # Basic Follower Info
            'follower_screen_name': follower.screen_name,
            # Booleans
            'follower_default_profile': int(follower.default_profile),
            'follower_default_profile_image': int(follower.default_profile_image),
            'follower_protected': int(follower.protected),
            'follower_verified': int(follower.verified),
            # Numbers
            'follower_favourites_count': follower.favourites_count,
            'follower_followers_count': follower.followers_count,
            'follower_friends_count': follower.friends_count,
            'follower_listed_count': follower.listed_count,
            'follower_statuses_count': follower.statuses_count,
            # Strings
            'follower_created_at': str(follower.created_at),
            'follower_description': follower.description or '',
            'follower_location': follower.location or '',
            'follower_name': follower.name,
            'follower_url': follower.url or '',
            'follower_withheld_in_countries': withheld_countries,
            'follower_withheld_scope': getattr(follower, 'withheld_scope', ''),
            # Basic Account Info
            'account_id': str(account.id),
            'account_screen_name': account.screen_name,
        }

    # Memoize seen account.
    FOLLOWERS_SEEN[str(follower.id)] = {
        'screen_name': follower.screen_name,
    }


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
