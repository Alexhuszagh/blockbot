blockbot
========

High-level utilities to make Twitter tolerable.

**Table of Contents**

- [Features](#features)
- [Getting Started](#getting-started)
- [License](#license)
- [Contributing](#contributing)

# Features

- Block Followers of an Account
- Block Media Replies

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

## Block Followers of An Account

Twitter has a major harassment problem, leading to "dogpiles". Often, a problematic user quotes a Tweet of yours, leading to large groups of their followers harassment you. blockbot allows you to block all followers of an account, to help stem the tide of harassment:

```python
import blockbot

# List of accounts to block followers from.
accounts = ['twitter']
# Optional list of accounts to whitelist: don't block the account
# if they follow or are followed by @jack.
whitelist = ['jack']
blockbot.block_followers(accounts, whitelist)

# Valid keywords to customize blocking behavior:
#   whitelist_verified (default True) - Do not block verified accounts.
#   whitelist_following (default True) - Do not block accounts you follow.
#   whitelist_follow_request_sent (default True) - Do not block accounts you have sent follow requests to.
#   whitelist_friendship (default True) - Do not block accounts that follow you or you follow.
``` 

## Block Media Replies

Twitter has a major harassment problem, leading to "dogpiles". Often, a problematic user quotes a Tweet of yours, leading to large groups of their followers harassment you. blockbot allows you to block all followers of an account, to help stem the tide of harassment:

```python
import blockbot

# Block all replies to Tweets from @twitter with media in the replies.
screen_name = 'twitter'
# Optional list of accounts to whitelist: don't block the account
# if they follow or are followed by @jack.
whitelist = ['jack']
blockbot.block_media_reply(screen_name, whitelist)

# Valid keywords to customize blocking behavior:
#   whitelist_photo (default True) - Do not block media replies containing photos.
#   whitelist_animated_gif (default False) - Do not block media replies containing animated GIFs.
#   whitelist_video (default False) - Do not block media replies containing animated GIFs.
#   whitelist_verified (default True) - Do not block verified accounts.
#   whitelist_following (default True) - Do not block accounts you follow.
#   whitelist_follow_request_sent (default True) - Do not block accounts you have sent follow requests to.
#   whitelist_friendship (default True) - Do not block accounts that follow you or you follow.
``` 

# License

Lexical is licensed under the Apache 2.0 license. See the LICENSE for more information.

# Contributing

Unless you explicitly state otherwise, any contribution intentionally submitted for inclusion in lexical by you, as defined in the Apache-2.0 license, shall be licensed as above, without any additional terms or conditions.
