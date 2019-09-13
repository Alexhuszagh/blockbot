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

        account_screen_name = 'twitter'
        whitelist_screen_names = ['jack']
        blockbot.block_media_replies(account_screen_name, whitelist_screen_names)
'''

import tweepy

from . import api
from . import collections
from . import log
from . import whitelist

# Logger for BlockMediaReply.
LOGGER = log.new_logger('BlockMediaReplies')
# Previously processed tweets from account.
TWEETS_PROCESSED = collections.wired_tiger_dict(
    name='BlockMediaRepliesProcessedTweets',
    key_format='r',
    value_format='Sr',
    columns=('user_id', 'screen_name', 'max_id')
)
# Previously processed replies we don't want to re-process.
REPLIES_PROCESSED = collections.wired_tiger_dict(
    name='BlockMediaRepliesProcessedReplies',
    key_format='r',     # Original Tweet ID
    value_format='r',   # Max ID for the replies.
    columns=('tweet_id', 'max_id')
)
# Previously seen account screen names of repliers.
REPLIERS_SEEN = collections.wired_tiger_dict(
    name='BlockFollowersSeenRepliers',
    key_format='r',
    value_format='S',
    columns=('user_id', 'screen_name')
)
# Previously blocked account screen names of replier.
REPLIERS_BLOCKED = collections.wired_tiger_dict(
    name='BlockMediaRepliesBlockedRepliers',
    key_format='r',
    value_format='SbbbbQQQQQSSSSSSSrrSbbbQQSSSSSS',
    columns=(
        # Basic Replier Info
        'replier_id',
        'replier_screen_name',
        # Replier Booleans.
        'replier_default_profile',
        'replier_default_profile_image',
        'replier_protected',
        'replier_verified',
        # Replier Numbers.
        'replier_favourites_count',
        'replier_repliers_count',
        'replier_friends_count',
        'replier_listed_count',
        'replier_statuses_count',
        # Replier Strings
        'replier_created_at',
        'replier_description',
        'replier_location',
        'replier_name',
        'replier_url',
        'replier_withheld_in_countries',
        'replier_withheld_scope',
        # Basic Tweet Info
        'tweet_id',
        'tweet_author_id',
        'tweet_author_screen_name',
        # Reply Booleans
        'reply_is_quote_status',
        'reply_possibly_sensitive',
        'reply_withheld_copyright',
        # Reply Numbers
        'reply_retweet_count',
        'reply_favorite_count',
        # Reply Strings
        'reply_created_at',
        'reply_lang',
        'reply_source',
        'reply_withheld_in_countries',
        'reply_withheld_scope',
        # Media Basic Info
        'media_type',
    )
)


def tweets(tweepy_api, account):
    '''Get full Tweet objects for user timeline of account.'''

    # Get the current max_id for the tweets from account.
    id_state = api.IdState()
    if account.id in TWEETS_PROCESSED:
        id_state.max_id = TWEETS_PROCESSED[account.id][1]
    if id_state.max_id == api.END_MAX_ID:
        # Previously finished all Tweets from account, don't make any API requests.
        return

    try:
        for tweet in api.user_timeline(
            tweepy_api,
            screen_name=account.screen_name,
            id_state=id_state,
            logger=LOGGER,
        ):
            yield tweet
    except tweepy.TweepError:
        # Store the id state on an error and re-raise.
        TWEETS_PROCESSED[account.id] = (account.screen_name, id_state.max_id)
        raise

    # Store that all Tweets have been processed for account.
    TWEETS_PROCESSED[account.id] = (account.screen_name, api.END_MAX_ID)


def replies(tweepy_api, tweet, previous_id=None):
    '''Find replies to Tweet.'''

    id_state = api.IdState()
    if tweet.id in REPLIES_PROCESSED:
        id_state.max_id = REPLIES_PROCESSED[tweet.id]
    if id_state.max_id == api.END_MAX_ID:
        # Previously finished all replies to the tweet, don't make any API requests.
        return

    # Build our query and fetch Tweets.
    LOGGER.info(f'Finding replies to Tweet id {tweet.id}.')
    query = f'to:{tweet.user.screen_name} filter:media since_id:{tweet.id}'
    if previous_id is not None:
        query += f' max_id:{previous_id}'
    try:
        for reply in api.search(
            tweepy_api,
            query,
            count=100,
            result_type='recent',
            id_state=id_state,
            logger=LOGGER,
        ):
            yield reply
    except tweepy.TweepError:
        # Store the id state on an error and re-raise.
        REPLIES_PROCESSED[tweet.id] = id_state.max_id
        raise

    # Store that all replies have been processed for Tweet.
    REPLIES_PROCESSED[tweet.id] = api.END_MAX_ID


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
    if not 'media' in reply.extended_entities:
        # No media key in extended_entities, unexpected but be safe.
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


def block_account(tweepy_api, me, reply, tweet, user, whitelist_users, **kwds):
    '''Block account if not white-listed.'''

    # Allow repeated requests without incurring API limits.
    if user.id in REPLIERS_SEEN:
        return

    if whitelist.should_block_user(tweepy_api, me, user, whitelist_users, **kwds):
        if not getattr(user, 'blocking', False):
            tweepy_api.create_block(user_id=user.id)

        # Memoize blocked account.
        LOGGER.info(f'Blocked replier={user.screen_name}')
        media = reply.extended_entities['media'][0]
        REPLIERS_BLOCKED[user.id] = (
            # Basic Replier Info
            user.screen_name,
            # Booleans
            user.default_profile,
            user.default_profile_image,
            user.protected,
            user.verified,
            # Numbers
            user.favourites_count,
            user.followers_count,
            user.friends_count,
            user.listed_count,
            user.statuses_count,
            # Strings
            str(user.created_at),
            user.description or '',
            user.location or '',
            user.name,
            user.url or '',
            ','.join(getattr(user, 'withheld_in_countries', [])),
            getattr(user, 'withheld_scope', ''),
            # Basic Tweet Info
            tweet.id,
            tweet.user.id,
            tweet.user.screen_name,
            # Reply Booleans
            reply.is_quote_status,
            getattr(reply, 'possibly_sensitive', False),
            getattr(reply, 'withheld_copyright', False),
            # Reply Numbers
            getattr(reply, 'retweet_count', 0),
            getattr(reply, 'favorite_count', 0),
            # Reply Strings
            str(reply.created_at),
            getattr(reply, 'lang', ''),
            reply.source,
            ','.join(getattr(reply, 'withheld_in_countries', [])),
            getattr(reply, 'withheld_scope', ''),
            # Media Basic Info
            media['type'],
        )

    # Memoize seen account.
    REPLIERS_SEEN[user.id] = user.screen_name


def block_media_replies(
    account_screen_name,
    whitelist_screen_names=None,
    **kwds
):
    '''
    Block all users who reply to an account with media in their reply.

    :param account_screen_names:
        Screen name of account to find replies to.
    :param whitelist_screen_names:
        (Optional) Optional iterable of screen names to whitelist.
    :param **kwds:
        Optional keyword-arguments to override account whitelisting.

    .. code-block:: python

        account_screen_name = 'twitter'
        whitelist_screen_names = ['jack']
        block_media_replies(account_screen_name, whitelist_screen_names)
    '''

    tweepy_api = api.generate_api()
    me = tweepy_api.me()
    account = tweepy_api.get_user(screen_name=account_screen_name)
    whitelist = []
    if whitelist_screen_names is not None:
        whitelist = list(api.lookup_users(
            tweepy_api,
            screen_names=whitelist_screen_names,
            logger=LOGGER,
        ))

    previous_tweet_id = None
    for tweet in tweets(tweepy_api, account):
        for reply in replies(tweepy_api, tweet, previous_tweet_id):
            if should_block_media(reply, **kwds):
                block_account(tweepy_api, me, reply, tweet, reply.user, whitelist, **kwds)
        previous_tweet_id = tweet.id
