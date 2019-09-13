'''
    whitelist
    =========

    Optional utility to add a whitelist to certain accounts, which
    will not block the account if a certain condition is met.

    Whitelist will not suggest a block if:

    1. The account is verified (override with the `whitelist_verified=False`).
    2. You are following the account (override with `whitelist_following=False`).
    3. You sent the account a follow request (override with `whitelist_follow_request_sent=False`).
    4. The account follows you (override with `whitelist_friendship=False`).

    # Warnings

    The rate-limiting factor is the number of API calls, which increases
    exponentially with the number of whitelisted users.
'''


def has_friendship(tweepy_api, source, target):
    '''Check if there exists a friendship between two users.'''

    # Will return two friendships, in arbitrary order. We just want either
    # following or followed_by.
    friendship = tweepy_api.show_friendship(
        source_screen_name=source.screen_name,
        target_screen_name=target.screen_name
    )[0]
    return friendship.following or friendship.followed_by


def should_block_user(tweepy_api, me, user, whitelist, **kwds):
    '''Checks if a user is whitelisted..'''

    if kwds.get('whitelist_verified', True) and user.verified:
        # Do not block verified accounts.
        return False
    if kwds.get('whitelist_following', True) and user.following:
        # Do not block accounts if following them.
        return False
    elif kwds.get('whitelist_follow_request_sent', True) and user.follow_request_sent:
        # Do not block accounts if you sent a follow request to them.
        return False
    elif kwds.get('whitelist_friendship', True) and has_friendship(tweepy_api, user, me):
        # Do not block accounts if you have a friendship with the user.
        return False
    # Do not block accounts if they have a friendship with whitelisted accounts.
    return not any(has_friendship(tweepy_api, user, i) for i in whitelist)
