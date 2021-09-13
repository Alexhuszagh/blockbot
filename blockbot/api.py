'''
    api
    ===

    High-level utility to access the Twitter API.

    Update config/api.json to update credentials.
'''

import collections
import dataclasses
import json
import os
import time
import tweepy
import typing

from . import path
from . import util

# STATE
# -----

START_MAX_ID = None
END_MAX_ID = 0

START_CURSOR = -1
END_CURSOR = 0

START_PAGE = 0

# Default timeout is set to 5 seconds.
DEFAULT_TIMEOUT = 5


@dataclasses.dataclass
class IdState:
    '''Store current state for identifier.'''
    max_id: typing.Optional[int] = START_MAX_ID


@dataclasses.dataclass
class CursorState:
    '''Store current state for cursor.'''
    next_cursor: int = START_CURSOR


@dataclasses.dataclass
class PageState:
    '''Store current state for page.'''
    current_page: int = START_PAGE


# ERRORS
# ------


def is_connection_error(error):
    '''Determine if an error is a connection error.'''
    return error.reason.startswith('Failed to send request: HTTPSConnectionPool')


def is_authorization_error(error):
    '''Determine if an error is a authorization error.'''
    return error.reason.startswith((
        'Not authorized.',
        'Twitter error response: status code = 401',
    ))

def is_user_not_found_error(error):
    '''Determine if the error is due to a user not being found.'''
    return error.api_code == 50

# RATE LIMIT


def minutes_to_ns(minutes):
    '''Convert minutes (as an integer) into nanoseconds.'''
    return minutes * 60 * 10**9


def hours_to_ns(hours):
    '''Convert hours (as an integer) into nanoseconds.'''
    return 60 * minutes_to_ns(hours)


class RateLimit:
    '''A specialized storage for a rate limit type.'''

    def __init__(self, limit, interval):
        self._limit = limit
        self._interval = interval
        # This is a FIFO queue, where the left-most elements
        # are the most recent aditions.
        self._deque = collections.deque(maxlen=limit)

    def wait(self):
        '''Try to make a call, and if so, wait.'''

        if len(self._deque) == self._limit:
            start = self._deque.pop()
            diff = time.time_ns() - start
            wait_time = (self._interval - diff) / 10**9
            time.sleep(max(wait_time, 0.0))
        self._deque.appendleft(time.time_ns())


# API
# ---

TimeLimit = collections.namedtuple('TimeLimit', 'limit interval')

# These take the minimum for the current user or the app,
# to ensure the limit isn't reached. They're adapted for
# 15 minute windows, the original interval may be longer.
API_V11_LIMITS = {
    'update_status': TimeLimit(300, hours_to_ns(3)),
    'retweet': TimeLimit(300, hours_to_ns(3)),
    'create_favorite': TimeLimit(1000, hours_to_ns(24)),
    'create_friendship': TimeLimit(400, hours_to_ns(24)),
    'send_direct_message': TimeLimit(1000, hours_to_ns(24)),
    'verify_credentials': TimeLimit(75, minutes_to_ns(15)),
    'rate_limit_status': TimeLimit(180, minutes_to_ns(15)),
    'get_favorites': TimeLimit(75, minutes_to_ns(15)),
    'get_follower_ids': TimeLimit(15, minutes_to_ns(15)),
    'get_followers': TimeLimit(15, minutes_to_ns(15)),
    'get_friend_ids': TimeLimit(15, minutes_to_ns(15)),
    'get_friends': TimeLimit(15, minutes_to_ns(15)),
    'get_friendship': TimeLimit(180, minutes_to_ns(15)),
    'geo_id': TimeLimit(75, minutes_to_ns(15)),
    'supported_languages': TimeLimit(15, minutes_to_ns(15)),
    'get_lists': TimeLimit(15, minutes_to_ns(15)),
    'get_list_members': TimeLimit(900, minutes_to_ns(15)),
    'get_list_member': TimeLimit(15, minutes_to_ns(15)),
    'get_list_memberships': TimeLimit(75, minutes_to_ns(15)),
    'get_list_ownerships': TimeLimit(15, minutes_to_ns(15)),
    'get_list': TimeLimit(75, minutes_to_ns(15)),
    'list_timeline': TimeLimit(900, minutes_to_ns(15)),
    'get_list_subscribers': TimeLimit(180, minutes_to_ns(15)),
    'get_list_subscriber': TimeLimit(15, minutes_to_ns(15)),
    'get_list_subscriptions': TimeLimit(15, minutes_to_ns(15)),
    'search_tweets': TimeLimit(180, minutes_to_ns(15)),
    'lookup_statuses': TimeLimit(900, minutes_to_ns(15)),
    'mentions_timeline': TimeLimit(75, minutes_to_ns(15)),
    'get_retweeter_ids': TimeLimit(75, minutes_to_ns(15)),
    'get_retweets_of_me': TimeLimit(75, minutes_to_ns(15)),
    'get_retweets': TimeLimit(75, minutes_to_ns(15)),
    'get_status': TimeLimit(900, minutes_to_ns(15)),
    'user_timeline': TimeLimit(900, minutes_to_ns(15)),
    'available_trends': TimeLimit(75, minutes_to_ns(15)),
    'closest_trends': TimeLimit(75, minutes_to_ns(15)),
    'get_place_trends': TimeLimit(75, minutes_to_ns(15)),
    'lookup_users': TimeLimit(900, minutes_to_ns(15)),
    'search_users': TimeLimit(900, minutes_to_ns(15)),
    'get_user': TimeLimit(900, minutes_to_ns(15)),
}

API_V2_LIMITS = {
    'retweet': TimeLimit(300, hours_to_ns(3)),
    'unretweet': TimeLimit(1000, hours_to_ns(24)),
    'create_block': TimeLimit(50, minutes_to_ns(15)),
    'destroy_block': TimeLimit(50, minutes_to_ns(15)),
    'create_mute': TimeLimit(50, minutes_to_ns(15)),
    'destroy_mute': TimeLimit(50, minutes_to_ns(15)),
    'get_blocks': TimeLimit(15, minutes_to_ns(15)),
    'get_retweets': TimeLimit(75, minutes_to_ns(15)),
    'create_favorite': TimeLimit(1000, hours_to_ns(24)),
    'destroy_favorite': TimeLimit(1000, hours_to_ns(24)),
    'get_favorites': TimeLimit(75, minutes_to_ns(15)),
    'search_tweets': TimeLimit(180, minutes_to_ns(15)),
    'mentions_timeline': TimeLimit(180, minutes_to_ns(15)),
    'user_timeline': TimeLimit(900, minutes_to_ns(15)),
    'lookup_statuses': TimeLimit(900, minutes_to_ns(15)),
    'get_status': TimeLimit(900, minutes_to_ns(15)),
    'get_followers': TimeLimit(15, minutes_to_ns(15)),
    'create_friendship': TimeLimit(400, hours_to_ns(500)),
    'destroy_friendship': TimeLimit(500, hours_to_ns(500)),
    'lookup_users': TimeLimit(900, minutes_to_ns(15)),
    'get_user': TimeLimit(900, minutes_to_ns(15)),
}


class API:
    '''
    Wrapper around the Tweepy API with custom rate limits.

    This is somewhat necessary, since Tweepy does not recognize
    the new Twitter APIv2 rate limits, and therefore can cause apps
    to get blocked. There's also the issue of the extremely low limits,
    and how this differs with corporate/non-corporate accounts.

    Note: you may have to specify your own version of the API root,
    if not provided, since recent versions of Tweepy have deprecated this.
    '''

    _slots_ = ('api', 'api_root', 'local_rate_limit', 'limits')

    def __init__(self, api, api_root=None, local_rate_limit=False):
        self.api = api
        self.api_root = api_root
        if api_root is None:
            self.api_root = getattr(api, 'api_root', '/1.1')
        self.local_rate_limit = local_rate_limit
        self.limits = {}

    def wait_limit(self, method):
        '''Determine the appropriate wait for the current API version.'''

        # Get our approach rate limit.
        try:
            if not self.local_rate_limit:
                # Let Tweepy do the heavy lifting.
                return
            elif self.api_root in ('/1', '/1.1'):
                # Version 1/1.1 API.
                limit = API_V11_LIMITS[method]
            elif self.api_root == '/2':
                # Version 2 API. Some of these still allow v1.1 access.
                limit = API_V2_LIMITS.get(method)
                if limit is None:
                    limit = API_V11_LIMITS[method]
            else:
                raise ValueError('Invalid API root version.')
        except KeyError:
            # No special known rate limits, just return.
            return

        # Now, construct our rate limiter and wait.
        if method not in self.limits:
            self.limits[method] = RateLimit(limit.limit, limit.interval)
        self.limits[method].wait()

    def call(self, limit, names, *args, **kwds):
        '''Call a Tweepy API method. Note that these endpoints might have aliases.'''

        self.wait_limit(limit)
        # We might have renamed methods, iterate over those.
        for name in names:
            method = getattr(self.api, name, None)
            if method is not None:
                return method(*args, **kwds)

        raise ValueError('No suitable methods found.')

    def __getattr__(self, attr):
        '''Fallback to call the proper low-level method if not provided.'''
        return getattr(self.api, attr)

    def user_timeline(self, *args, **kwds):
        return self.call('user_timeline', ['user_timeline'], *args, **kwds)

    user_timeline.pagination_mode = 'id'

    # User methods

    def get_user(self, *args, **kwds):
        return self.call('get_user', ['get_user'], *args, **kwds)

    def me(self):
        # Removed in Tweepy 4.0
        return self.get_user(screen_name=self.api.auth.get_username())

    def get_followers(self, *args, **kwds):
        names = ['get_followers', 'followers']
        return self.call('get_followers', names, *args, **kwds)

    get_followers.pagination_mode = 'cursor'

    # Friendship Methods

    def get_friendship(self, *args, **kwds):
        names = ['get_friendship', 'show_friendship']
        return self.call('get_friendship', names, *args, **kwds)

    # Account Methods

    def verify_credentials(self, *args, **kwds):
        return self.call('verify_credentials', ['verify_credentials'], *args, **kwds)

    def rate_limit_status(self, *args, **kwds):
        return self.call('rate_limit_status', ['rate_limit_status'], *args, **kwds)

    # Block Methods

    def create_block(self, *args, **kwds):
        return self.call('create_block', ['create_block'], *args, **kwds)

    def destroy_block(self, *args, **kwds):
        return self.call('destroy_block', ['destroy_block'], *args, **kwds)

    def get_blocks(self, *args, **kwds):
        names = ['get_blocks', 'blocks']
        return self.call('get_blocks', names, *args, **kwds)

    # Help Methods

    def search_tweets(self, *args, **kwds):
        names = ['search_tweets', 'search']
        return self.call('search_tweets', names, *args, **kwds)

    search_tweets.pagination_mode = 'id'


def generate_api(
    timeout=DEFAULT_TIMEOUT,
    api_root=None,
    local_rate_limit=None,
):
    '''Generate the API from config.'''

    with open(os.path.join(path.config_dir(), 'api.json')) as f:
        api_data = json.load(f)

    consumer_key = api_data['consumer_key']
    consumer_secret = api_data['consumer_secret']
    access_token = api_data['access_token']
    access_token_secret = api_data['access_token_secret']
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    if api_root is None:
        api_root = api_data.get('api_root')
    if local_rate_limit is None:
        local_rate_limit = api_data.get('local_rate_limit', False)

    tweepy_api = tweepy.API(
        auth,
        timeout=timeout,
        wait_on_rate_limit=True,
        wait_on_rate_limit_notify=True,
        compression=True
    )
    return API(tweepy_api, api_root, local_rate_limit)


def lookup_users(
    api,
    user_ids=None,
    screen_names=None,
    page_state=None,
    logger=None,
):
    '''
    Lookup user accounts. Must provide `user_ids` or `screen_names`.

    :param api: Tweepy API instance.
    :param user_ids: (Optional) Iterable of user IDs.
    :param screen_names: (Optional) Iterable of screen names.
    :param page_state: (Optional) Current page state of iterator.
    :param logger: (Optional) Log file to record data to.

    .. code-block:: python

        api = generate_api()
        screen_names = ['twitter']
        page_state = PageState()
        for user in lookup_users(
            api,
            screen_names=screen_names,
            page_state=page_state
        ):
            print(user.id)
    '''

    # Constants
    page_size = 100

    def bind_api(param, iterable, current_page):
        start_index = current_page * page_size
        for chunk in util.chunks(iterable, page_size, start_index):
            for user in api.lookup_users(**{param: chunk}):
                yield user

            # Increment state after fetching users.
            if page_state is not None:
                page_state.current_page += 1

    # Can handle up to 100 users per request.
    current_page = START_PAGE
    if page_state is not None:
        current_page = page_state.current_page

    if logger is not None:
        logger.info(f'Calling Twitter API.lookup_users.')

    # Cannot error except for a network error.
    if user_ids is not None:
        return bind_api('user_ids', user_ids, current_page)
    elif screen_names is not None:
        return bind_api('screen_names', screen_names, current_page)
    raise ValueError('Must provide user_ids or screen_names.')


def get_followers(
    api,
    user_id=None,
    screen_name=None,
    cursor_state=None,
    logger=None,
):
    '''
    Get followers of account.

    :param api: Tweepy API instance.
    :param user_ids: (Optional) User IDs.
    :param screen_names: (Optional) Screen name.
    :param cursor_state: (Optional) Current cursor state of iterator.
    :param logger: (Optional) Log file to record data to.

    .. code-block:: python

        api = generate_api()
        screen_name = 'twitter'
        cursor_state = CursorState()
        for user in followers(
            api,
            screen_name=screen_name,
            cursor_state=cursor_state
        ):
            print(user.id)
    '''

    next_cursor = START_CURSOR
    if cursor_state is not None:
        next_cursor = cursor_state.next_cursor

    if logger is not None:
        logger.info(f'Calling Twitter API.followers.')

    cursor = tweepy.Cursor(
        api.get_followers,
        user_id=user_id,
        screen_name=screen_name,
        cursor=next_cursor,
    )
    try:
        for page in cursor.pages():
            yield from page

            # Increment state after fetching followers.
            if cursor_state is not None:
                cursor_state.next_cursor = cursor.iterator.next_cursor
    except tweepy.TweepError as error:
        if is_authorization_error(error):
            if logger is not None:
                logger.warn(f'Unauthorized to get followers for account user_id={user_id}, screen_name={screen_name}.')
        else:
            # Only expect authorization errors, due to user blocking/protected
            # status. Raise all errors.
            raise


def user_timeline(
    api,
    user_id=None,
    screen_name=None,
    id_state=None,
    logger=None,
):
    '''
    Get user timeline of account.

    :param api: Tweepy API instance.
    :param user_ids: (Optional) User IDs.
    :param screen_names: (Optional) Screen name.
    :param id_state: (Optional) Current id state of iterator.
    :param logger: (Optional) Log file to record data to.

    .. code-block:: python

        api = generate_api()
        screen_name = 'twitter'
        id_state = IdState()
        for tweet in user_timeline(
            api,
            screen_name=screen_name,
            id_state=id_state
        ):
            print(tweet.id)
    '''

    max_id = START_MAX_ID
    if id_state is not None:
        max_id = id_state.max_id

    if logger is not None:
        logger.info(f'Calling Twitter API.user_timeline.')

    cursor = tweepy.Cursor(
        api.user_timeline,
        user_id=user_id,
        screen_name=screen_name,
        max_id=max_id,
    )
    try:
        for page in cursor.pages():
            yield from page

            # Increment state after fetching user timeline.
            if id_state is not None:
                id_state.max_id = cursor.iterator.max_id
    except tweepy.TweepError as error:
        if is_authorization_error(error):
            if logger is not None:
                logger.warn(f'Unauthorized to get user timeline for account user_id={user_id}, screen_name={screen_name}.')
        else:
            # Only expect authorization errors, due to user blocking/protected
            # status. Raise all errors.
            raise


def search_tweets(
    api,
    query,
    logger=None,
    id_state=None,
    **kwds
):
    '''
    Perform Twitter search.

    :param api: Tweepy API instance.
    :param q: Search query.
    :param geocode: (Optional) Return Tweets from users in the geocode.
    :param lang: (Optional) Return Tweets with the given language.
    :param locale: (Optional) Language of query sent.
    :param result_type: (Optional) Type of search results to receive.
    :param count: (Optional) Number of Tweets to return (max 100, default 15).
    :param until: (Optional) Return Tweets before date, as YYYY-MM-DD.
    :param include_entities: (Optional) Do not include entities node if set to false.
    :param id_state: (Optional) Current id state of iterator.
    :param logger: (Optional) Log file to record data to.

    .. code-block:: python

        api = generate_api()
        q = 'to:twitter from:jack'
        id_state = IdState()
        for tweet in search(
            api,
            q,
            id_state=id_state
        ):
            print(tweet.id)
    '''

    max_id = START_MAX_ID
    if id_state is not None:
        max_id = id_state.max_id

    if logger is not None:
        logger.info(f'Calling Twitter API.search_tweets.')

    cursor = tweepy.Cursor(
        api.search_tweets,
        q=query,
        max_id=max_id,
        **kwds
    )
    # Cannot error except for a network error.
    for page in cursor.pages():
        yield from page

        # Increment state after search results.
        if id_state is not None:
            id_state.max_id = cursor.iterator.max_id


def create_block(api, user_id):
    '''Try and create a block for a given user.'''

    try:
        api.create_block(user_id=user_id)
    except tweepy.TweepError as error:
        if is_user_not_found_error(error):
            # Use deactivated their account while processing.
            return
        raise
