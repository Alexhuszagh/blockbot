'''
    log
    ===

    High-level logger for API requests.
'''

import datetime
import logging
import os

from . import path

def log_name():
    '''Get date/time-based log name.'''
    return '{:%Y-%m-%d-%H-%M-%S}.log'.format(datetime.datetime.now())

def new_logger(name):
    '''Define a new logger.'''

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Add the handlers to logger
    logger.addHandler(STREAM_HANDLER)
    logger.addHandler(FILE_HANDLER)

    return logger

def override_tweepy_logger(tweepy):
    '''Override the Tweepy logger with the Tweepy module and a logger object.'''

    # This isn't documented, and likely not stable, but it works.
    # And we kind of need this information. It hasn't changed since
    # Nov. 15, 2014, so we should be safe.
    logger = tweepy.binder.log

    # Add the handlers to logger
    logger.addHandler(STREAM_HANDLER)
    logger.addHandler(FILE_HANDLER)


os.makedirs(path.log_dir(), exist_ok=True)
CURRENT_LOG_NAME = log_name()
CURRENT_LOG_PATH = os.path.join(path.log_dir(), CURRENT_LOG_NAME)

# File Handler
FILE_HANDLER = logging.FileHandler(CURRENT_LOG_PATH)
FILE_HANDLER.setLevel(logging.DEBUG)

# Stderr Handler
STREAM_HANDLER = logging.StreamHandler()
STREAM_HANDLER.setLevel(logging.WARNING)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
STREAM_HANDLER.setFormatter(formatter)
FILE_HANDLER.setFormatter(formatter)
