blockbot
========

High-level utilities to make Twitter tolerable.

**Table of Contents**

- [Features](#features)
- [Getting Started](#getting-started)
- [Daemons](#daemons)
- [Thread Safety](#thread-safety)
- [License](#license)
- [Contributing](#contributing)

# Features

- Block Followers of an Account
- Block Media Replies
- Long-Running Queries (Daemons) 

# Getting Started

blockbot requires a somewhat dev-friendlty environment, since it uses WiredTiger for a high-performance backing store. blockbot therefore requires:

1. Python 3.7 or higher.
2. A C compiler and autotools (`build-essential` on Ubuntu).
2. Snappy (`libsnappy-dev` on Ubuntu).

Next, install blockbot from source:

```bash
python setup.py install --user
```

## Configuring API Access

blockbot requires API access, and does this through Tweepy. In order to access Tweepy, you must update [config/api.json](config/api.json) with your credentials acquired from [Twitter Developer](https://developer.twitter.com/).

## High-Level Access

First, edit the configuration files in `~/.blockbot/config/`. You will need to edit `api.json` and the config for the script you wish to use.

A dummy example of API JSON with realistic but fake data is:

```json
{
    "consumer_key": "AIbwRVbCJMkaiQVlfJbKG5gAy",
    "consumer_secret": "P0wiBhrdNlCTb2okvzxRGNKD4opnyOtFGM7Q6Hvmig0IzjMYw5",
    "access_token": "Q9D4wOv9zA-q3rlIxbZgknaZKaPwGBPtiT4AcQLWZ5Q9lduhX7",
    "access_token_secret": "lXyoz2kDkSz01riCAkbOlE4iOmSkBlHXVij"
}
```

For example, use `block_media_replies`, you would edit `block_media_replies.json` to have the desired data. An example would be:

```json
{
    "account_screen_name": "twitter",
    "whitelist_screen_names": ["jack"],
    "keywords": {
        "whitelist_photo": true,
        "whitelist_animated_gif": false,
        "whitelist_video": false,
        "whitelist_verified": true,
        "whitelist_following": true,
        "whitelist_follow_request_sent": true,
        "whitelist_friendship": true,
        "sleep_time": 600
    }
}
```

Finally, run `block_media_replies.py` (if it's not in the path, it should be installed in `~/.local/bin/block_media_replies.py`). Now, the script will run in the background blocking the most recent media replies to the account in question.

To kill the script, run `kill_block_media_replies.py`.

## Block Followers of An Account

Twitter has a major harassment problem, leading to "dogpiles". Often, a problematic user quotes a Tweet of yours, leading to large groups of their followers harassment you. blockbot allows you to block all followers of an account, to help stem the tide of harassment:

```python
import blockbot

# List of account screen names to block followers from.
account_screen_names = ['twitter']
# Optional list of account screen names to whitelist: don't block the account
# if they follow or are followed by @jack.
whitelist_screen_names = ['jack']
blockbot.block_followers(account_screen_names, whitelist_screen_names)

# Valid keywords to customize connection behavior:
#   sleep_time (default 600) - Seconds to sleep on a non-fatal connection error.

# Valid keywords to customize blocking behavior:
#   whitelist_verified (default True) - Do not block verified accounts.
#   whitelist_following (default True) - Do not block accounts you follow.
#   whitelist_follow_request_sent (default True) - Do not block accounts you have sent follow requests to.
#   whitelist_friendship (default True) - Do not block accounts that follow you or you follow.
``` 

## Block Media Replies

Twitter prioritizes "native" media, which means media is an intrusive form of content on Twitter. Recently, groups of accounts have started spamming videos in replies to popular trends or in the replies of popular accounts. blockbot allows you to block these accounts automatically:

```python
import blockbot

# Block all replies to Tweets from @twitter with media in the replies.
account_screen_name = 'twitter'
# Optional list of account screen names to whitelist: don't block the account
# if they follow or are followed by @jack.
whitelist_screen_names = ['jack']
blockbot.block_media_reply(account_screen_name, whitelist_screen_names)

# Valid keywords to customize connection behavior:
#   sleep_time (default 600) - Seconds to sleep on a non-fatal connection error.

# Valid keywords to customize blocking behavior:
#   whitelist_photo (default True) - Do not block media replies containing photos.
#   whitelist_animated_gif (default False) - Do not block media replies containing animated GIFs.
#   whitelist_video (default False) - Do not block media replies containing video.
#   whitelist_verified (default True) - Do not block verified accounts.
#   whitelist_following (default True) - Do not block accounts you follow.
#   whitelist_follow_request_sent (default True) - Do not block accounts you have sent follow requests to.
#   whitelist_friendship (default True) - Do not block accounts that follow you or you follow.
``` 

# Daemons

Daemons are long-running tasks that run as background processes. Daemons are ideally suited to a Twitter block bot, so we provide utility functions to convert any feature into a daemon.

Please note that only one tasks, whether it is a daemon or a function call, should be running at a single time.

```python
import blockbot

# Block all replies to Tweets from @twitter with media in the replies.
account_screen_name = 'twitter'
# Optional list of accounts to whitelist: don't block the account
# if they follow or are followed by @jack.
whitelist_screen_names = ['jack']
# Pass the function name as the first argument, and any arguments
# to the function after. This will start the task as a daemon.
# This will exit the current interpreter.
blockbot.as_daemon(
    blockbot.block_media_reply, 
    account_screen_name, 
    whitelist_screen_names
)
```

# Thread Safety

Please note that nothing in this library is thread- or process-safe, and should not be run in multiple threads or processes with multi-threading or multi-processing. Since the bottleneck is both network I/O and Twitter's rate limits, neither multi-threading nor multi-processing makes sense and will not be supported.

# License

Lexical is licensed under the Apache 2.0 license. See the LICENSE for more information.

# Contributing

Unless you explicitly state otherwise, any contribution intentionally submitted for inclusion in lexical by you, as defined in the Apache-2.0 license, shall be licensed as above, without any additional terms or conditions.

**Warning**

Make sure not to accidentally expose your Twitter credentials on pull requests. To avoid accidentally exposing credentials, run the following command after cloning the repository:

```bash
git update-index --assume-unchanged config/api.json
```

All commits with Twitter credentials anywhere in the git history will be automatically rejected, for account safety reasons.
