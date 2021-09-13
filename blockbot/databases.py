'''
    databases
    =========

    Access to all the database stores.
'''

from .block_followers import (
    ACCOUNTS_PROCESSED,
    FOLLOWERS_SEEN,
    FOLLOWERS_BLOCKED
)

from .block_media_replies import (
    TWEETS_PROCESSED,
    REPLIES_PROCESSED,
    REPLIERS_SEEN,
    REPLIERS_BLOCKED
)

def get_databases():
    '''Get a map of all the databases by-module.'''

    return {
        'block_followers': {
            'accounts_processed': ACCOUNTS_PROCESSED,
            'followers_seen': FOLLOWERS_SEEN,
            'followers_blocked': FOLLOWERS_BLOCKED,
        },
        'block_media_replies': {
            'tweets_processed': TWEETS_PROCESSED,
            'replies_processed': REPLIES_PROCESSED,
            'repliers_seen': REPLIERS_SEEN,
            'repliers_blocked': REPLIERS_BLOCKED
        }
    }
