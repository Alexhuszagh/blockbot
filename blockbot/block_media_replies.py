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

import os
import tweepy

from . import api
from . import collections
from . import log
from . import whitelist

# Logger for BlockMediaReply.
LOGGER = log.new_logger('BlockMediaReplies')
# Previously processed tweets from account.
TWEETS_PROCESSED = collections.sqlite_dict(
    table='block_media_replies_processed_tweets',
    columns=(
        ('user_id', 'TEXT', False),
        ('screen_name', 'TEXT', False),
        ('max_id', 'TEXT', True),
    ),
    primary_key='user_id',
)
# Previously processed replies we don't want to re-process.
REPLIES_PROCESSED = collections.sqlite_dict(
    table='block_media_replies_processed_replies',
    columns=(
        ('tweet_id', 'TEXT', False), # Original Tweet ID
        ('max_id', 'TEXT', True),    # Max ID for the replies.
    ),
    primary_key='tweet_id',
)
# Previously seen account screen names of repliers.
REPLIERS_SEEN = collections.sqlite_dict(
    table='block_followers_seen_repliers',
    columns=(
        ('user_id', 'TEXT', False),
        ('screen_name', 'TEXT', False),
    ),
    primary_key='user_id',
)
# Previously blocked account screen names of replier.
REPLIERS_BLOCKED = collections.sqlite_dict(
    table='block_media_replies_blocked_repliers',
    columns=(
        # Basic Replier Info
        ('replier_id', 'TEXT', False),
        ('replier_screen_name', 'TEXT', False),
        ('reply_id', 'TEXT', False),
        # Replier Booleans.
        ('replier_default_profile', 'INTEGER', False),
        ('replier_default_profile_image', 'INTEGER', False),
        ('replier_protected', 'INTEGER', False),
        ('replier_verified', 'INTEGER', False),
        # Replier Numbers.
        ('replier_favourites_count', 'INTEGER', False),
        ('replier_repliers_count', 'INTEGER', False),
        ('replier_friends_count', 'INTEGER', False),
        ('replier_listed_count', 'INTEGER', False),
        ('replier_statuses_count', 'INTEGER', False),
        # Replier Strings
        ('replier_created_at', 'TEXT', False),
        ('replier_description', 'TEXT', False),
        ('replier_location', 'TEXT', False),
        ('replier_name', 'TEXT', False),
        ('replier_url', 'TEXT', False),
        ('replier_withheld_in_countries', 'TEXT', False),
        ('replier_withheld_scope', 'TEXT', False),
        # Basic Tweet Info
        ('tweet_id', 'TEXT', False),
        ('tweet_author_id', 'TEXT', False),
        ('tweet_author_screen_name', 'TEXT', False),
        # Reply Booleans
        ('reply_is_quote_status', 'INTEGER', False),
        ('reply_possibly_sensitive', 'INTEGER', False),
        ('reply_withheld_copyright', 'INTEGER', False),
        # Reply Numbers
        ('reply_retweet_count', 'INTEGER', False),
        ('reply_favorite_count', 'INTEGER', False),
        # Reply Strings
        ('reply_created_at', 'TEXT', False),
        ('reply_lang', 'TEXT', False),
        ('reply_source', 'TEXT', False),
        ('reply_withheld_in_countries', 'TEXT', False),
        ('reply_withheld_scope', 'TEXT', False),
        # Media Basic Info
        ('media_type', 'TEXT', False),
        ('media_content_type', 'TEXT', False),  # CSV-delimited if multiple values
        ('media_url', 'TEXT', False),           # CSV-delimited if multiple values
    ),
    primary_key='replier_id',
)


def tweets(tweepy_api, account):
    '''Get full Tweet objects for user timeline of account.'''

    # Get the current max_id for the tweets from account.
    id_state = api.IdState()
    previous = TWEETS_PROCESSED.get(str(account.id))
    if previous is not None:
        id_state.max_id = int(previous['max_id'])
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
            LOGGER.info(f'Processing Tweet ID {tweet.id} from screen name {account.screen_name}.')
            yield tweet
    except tweepy.TweepError:
        # Store the id state on an error and re-raise.
        TWEETS_PROCESSED[str(account.id)] = {
            'screen_name': account.screen_name,
            'max_id': str(id_state.max_id),
        }
        raise

    # Store that all Tweets have been processed for account.
    TWEETS_PROCESSED[str(account.id)] = {
        'screen_name': account.screen_name,
        'max_id': str(api.END_MAX_ID),
    }


def replies(tweepy_api, tweet, previous_id=None):
    '''Find replies to Tweet.'''

    id_state = api.IdState()
    previous = REPLIES_PROCESSED.get(str(tweet.id))
    if previous is not None:
        id_state.max_id = int(previous['max_id'])
    if id_state.max_id == api.END_MAX_ID:
        # Previously finished all replies to the tweet, don't make any API requests.
        return

    # Build our query and fetch Tweets.
    LOGGER.info(f'Finding replies to Tweet id {tweet.id}.')
    query = f'to:{tweet.user.screen_name} filter:media since_id:{tweet.id}'
    if previous_id is not None:
        query += f' max_id:{previous_id}'
    try:
        count = 0
        for reply in api.search_tweets(
            tweepy_api,
            query,
            count=100,
            result_type='recent',
            id_state=id_state,
            logger=LOGGER,
        ):
            count += 1
            if count % 50 == 0 and count > 0:
                LOGGER.info(f'Processed {count} replies.')
            yield reply
    except tweepy.TweepError:
        # Store the id state on an error and re-raise.
        REPLIES_PROCESSED[str(tweet.id)] = {
            'max_id': str(id_state.max_id),
        }
        raise

    # Store that all replies have been processed for Tweet.
    REPLIES_PROCESSED[str(tweet.id)] = {
        'max_id': str(api.END_MAX_ID),
    }


def media_has_photo(media):
    '''Determine if the media contains a photo.'''
    return any(i['type'] == 'photo' for i in media)


def media_has_animated_gif(media):
    '''Determine if the media contains a gif.'''
    return any(i['type'] == 'animated_gif' for i in media)


def media_has_video(media):
    '''Determine if the media contains a video.'''
    return any(i['type'] == 'video' for i in media)


def should_block_media(tweet, **kwds):
    '''Determine if we should block an account based on tweet media.'''

    if not hasattr(tweet, 'extended_entities'):
        # No native media, cannot have any videos in replies.
        return False
    if not 'media' in tweet.extended_entities:
        # No media key in extended_entities, unexpected but be safe.
        return False

    media = tweet.extended_entities['media']
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


def photo_mime_type(url):
    '''Extract the photo MIME type.'''

    suffix = os.path.splitext(url)[1]
    if suffix == '.jpg' or suffix == '.jpeg':
        return 'image/jpeg'
    elif suffix == '.gif':
        return 'image/gif'
    elif suffix == '.png':
        return 'image/png'
    else:
        raise ValueError('Unrecognized photo type.')


def extract_photo_media_url(media):
    '''Extract the media URL from a media extended entity type for a photo.'''

    # Photos store the photo type in the media url.
    urls = [i['media_url_https'] for i in media]
    mime_types = [photo_mime_type(url) for url in urls]

    return ','.join(mime_types), ','.join(urls)


def is_valid_video_type(content_type):
    '''Determine if the video format is a recognized format.'''
    return content_type in (
        'video/quicktime',
        'video/mp4',
    )


def extract_video_media_url(media):
    '''Extract the media URL from a media extended entity type for a video.'''

    # Can be a video or animated gif
    # Filter for actual video variants.
    variants = media['video_info']['variants']
    filtered = [i for i in variants if is_valid_video_type(i['content_type'])]
    if not filtered:
        raise ValueError(f'Could not get valid video variants, content-type is {variants[0]["content_type"]}.')

    # Choose the highest-quality variant.
    best = max(filtered, key=lambda x: x['bitrate'])
    return (best['content_type'], best['url'])


def extract_media_url(tweet):
    '''Extract the media URL from a Tweet.'''

    media = tweet.extended_entities['media']
    if len(media) == 0:
        raise ValueError('Got empty media list.')
    if media[0]['type'] == 'photo':
        # Can contain up to 4 photos.
        return extract_photo_media_url(media)
    elif len(media) > 1:
        raise ValueError('Got more than 1 media type for a non-photo type.')
    return extract_video_media_url(media[0])


def block_account(tweepy_api, me, reply, tweet, user, whitelist_users, **kwds):
    '''Block account if not white-listed.'''

    # Allow repeated requests without incurring API limits.
    if str(user.id) in REPLIERS_SEEN:
        LOGGER.info(f'Already blocked replier={user.screen_name}')
        return

    if whitelist.should_block_user(tweepy_api, me, user, whitelist_users, **kwds):
        if not getattr(user, 'blocking', False):
            api.create_block(tweepy_api, user.id)

        # Memoize blocked account.
        LOGGER.info(f'Blocked replier={user.screen_name}')
        media_content_type, media_url = extract_media_url(reply)
        media = reply.extended_entities['media'][0]
        user_withheld_countries = ','.join(getattr(user, 'withheld_in_countries', []))
        reply_withheld_countries = ','.join(getattr(reply, 'withheld_in_countries', []))
        REPLIERS_BLOCKED[str(user.id)] = {
            # Basic Reply Info
            'replier_screen_name': user.screen_name,
            'reply_id': str(reply.id),
            # Booleans
            'replier_default_profile': int(user.default_profile),
            'replier_default_profile_image': int(user.default_profile_image),
            'replier_protected': int(user.protected),
            'replier_verified': int(user.verified),
            # Numbers
            'replier_favourites_count': user.favourites_count,
            'replier_repliers_count': user.followers_count,
            'replier_friends_count': user.friends_count,
            'replier_listed_count': user.listed_count,
            'replier_statuses_count': user.statuses_count,
            # Strings
            'replier_created_at': str(user.created_at),
            'replier_description': user.description or '',
            'replier_location': user.location or '',
            'replier_name': user.name,
            'replier_url': user.url or '',
            'replier_withheld_in_countries': user_withheld_countries,
            'replier_withheld_scope': getattr(user, 'withheld_scope', ''),
            # Basic Tweet Info
            'tweet_id': str(tweet.id),
            'tweet_author_id': str(tweet.user.id),
            'tweet_author_screen_name': tweet.user.screen_name,
            # Reply Booleans
            'reply_is_quote_status': int(reply.is_quote_status),
            'reply_possibly_sensitive': int(getattr(reply, 'possibly_sensitive', False)),
            'reply_withheld_copyright': int(getattr(reply, 'withheld_copyright', False)),
            # Reply Numbers
            'reply_retweet_count': getattr(reply, 'retweet_count', 0),
            'reply_favorite_count': getattr(reply, 'favorite_count', 0),
            # Reply Strings
            'reply_created_at': str(reply.created_at),
            'reply_lang': getattr(reply, 'lang', ''),
            'reply_source': reply.source,
            'reply_withheld_in_countries': reply_withheld_countries,
            'reply_withheld_scope': getattr(reply, 'withheld_scope', ''),
            # Media Basic Info
            'media_type': media['type'],
            'media_content_type': media_content_type,
            'media_url': media_url,
        }

    # Memoize seen account.
    REPLIERS_SEEN[str(user.id)] = {
        'screen_name': user.screen_name,
    }


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

    timeout = kwds.pop('timeout', api.DEFAULT_TIMEOUT)
    api_root = kwds.pop('api_root', None)
    local_rate_limit = kwds.pop('local_rate_limit', None)
    tweepy_api = api.generate_api(timeout, api_root, local_rate_limit)
    tweepy_api = api.generate_api(timeout)
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
