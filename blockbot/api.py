'''
    api
    ===

    High-level utility to access the Twitter API.

    Update config/api.json to update credentials.
'''

import dataclasses
import json
import os
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


# API
# ---

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


def followers(
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
        api.followers,
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


def search(
    api,
    q,
    geocode=None,
    lang=None,
    locale=None,
    result_type=None,
    count=None,
    until=None,
    include_entities=None,
    id_state=None,
    logger=None,
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
        logger.info(f'Calling Twitter API.search.')

    cursor = tweepy.Cursor(
        api.search,
        q=q,
        geocode=geocode,
        lang=lang,
        locale=locale,
        result_type=result_type,
        count=count,
        until=until,
        include_entities=include_entities,
        max_id=max_id,
    )
    # Cannot error except for a network error.
    for page in cursor.pages():
        yield from page

        # Increment state after search results.
        if id_state is not None:
            id_state.max_id = cursor.iterator.max_id
