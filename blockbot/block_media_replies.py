'''
    block_media_replies
    ===================

    Block all accounts that reply to an account with media in their reply.

    Block media **does** not block an account if the account is
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

        screen_name = 'twitter'
        whitelist = ['jack']
        blockbot.block_media_replies(screen_name, whitelist)
'''

import tweepy

from . import api
from . import collections
from . import log
from . import whitelist

# Logger for BlockMediaReply.
LOGGER = log.new_logger('BlockMediaReplies')
# Previously processed Tweets we don't want to re-process.
TWEETS_PROCESSED = collections.wired_tiger_dict(
    name='BlockMediaRepliesProcessedTweets',
    value_format='r'    # max_id
)
# Previously seen account screen names of repliers.
ACCOUNTS_SEEN = collections.wired_tiger_set(
    name='BlockMediaRepliesSeenReplyAccounts'
)
# Previously blocked account screen names of replier.
ACCOUNTS_BLOCKED = collections.wired_tiger_dict(
    name='BlockMediaRepliesBlockedReplyAccounts',
    key_format='S',         # screen name
    value_format='S',       # offending Tweet
)


def tweets(api, screen_name):
    '''Get full Tweet objects for'''

    LOGGER.info(f'Getting tweets for {screen_name}.')
    try:
        for status in tweepy.Cursor(api.user_timeline, screen_name=screen_name).items():
            yield status
    except tweepy.TweepError:
        LOGGER.warn(f'Unable to get tweets for account {screen_name}')


def replies(api, tweet, previous_id=None):
    '''Find replies to Tweet.'''

    max_id = TWEETS_PROCESSED.get(tweet.id_str)
    if max_id == 0:
        # Previously finished the tweet, don't make any API requests.
        return

    LOGGER.info(f'Finding replies to Tweet id {tweet.id}.')
    query = f'to:{tweet.user.screen_name} since_id:{tweet.id}'
    if previous_id is not None:
        query += f' max_id:{previous_id}'
    try:
        curr = tweepy.Cursor(
            api.search,
            q=query,
            count=100,
            max_id=max_id
        )
        for page in curr.pages():
            yield from page
            TWEETS_PROCESSED[tweet.id_str] = curr.iterator.max_id
    except tweepy.TweepError:
        LOGGER.warn(f'Unable to get replies to Tweet {tweet.id}')

    # Store that all replies have been processed for Tweet.
    TWEETS_PROCESSED[tweet.id_str] = 0


def media_has_photo(media):
    '''Determine if the media contains a photo.'''
    return any(i['type'] == 'photo' for i in media)


def media_has_animated_gif(media):
    '''Determine if the media contains a gif.'''
    return any(i['type'] == 'animated_gif' for i in media)


def media_has_video(media):
    '''Determine if the media contains a video.'''
    return any(i['type'] == 'video' for i in media)


def should_block_media(reply, **kwds):
    '''Determine if we should block an account based on reply media.'''

    if not hasattr(reply, 'extended_entities'):
        # No native media, cannot have any videos in replies.
        return False

    media = reply.extended_entities['media']
    has_photo = media_has_photo(media)
    has_animated_gif = media_has_animated_gif(media)
    has_video = media_has_video(media)

    if not kwds.get('whitelist_photo', True) and has_photo:
        return True
    elif not kwds.get('whitelist_animated_gif', False) and has_animated_gif:
        return True
    elif not kwds.get('whitelist_video', False) and has_video:
        return True
    return False


def block_account(api, me, reply, user, whiteset, **kwds):
    '''Block account if not white-listed.'''

    if user.screen_name in ACCOUNTS_SEEN:
        return

    if whitelist.should_block_user(api, me, user, whiteset, **kwds):
        if not getattr(user, 'blocking', False):
            api.create_block(screen_name=user.screen_name)

        # Memoize blocked account.
        LOGGER.info(f'Blocked user={user.screen_name}')
        ACCOUNTS_BLOCKED[user.screen_name] = reply.id_str

    # Memoize seen account.
    ACCOUNTS_SEEN.add(user.screen_name)


def block_media_replies(screen_name, whitelist=None, **kwds):
    '''
    Block all users who reply to an account with media in their reply.

    :param screen_name: Screen name of account to find replies to.
    :param whitelist: (Optional) Optional iterable of screen names to whitelist.
    :param **kwds: Optional keyword-arguments to override account whitelisting.
    '''

    tweepy_api = api.generate_api()
    me = tweepy_api.me()
    whiteset = set(whitelist or [])
    previous_tweet_id = None
    for tweet in tweets(tweepy_api, screen_name):
        for reply in replies(tweepy_api, tweet, previous_tweet_id):
            if should_block_media(reply, **kwds):
                block_account(tweepy_api, me, reply, reply.user, whiteset, **kwds)
        previous_tweet_id = tweet.id
