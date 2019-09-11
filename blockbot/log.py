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


CURRENT_LOG_NAME = log_name()

# File Handler
FILE_HANDLER = logging.FileHandler(os.path.join(path.log_dir(), CURRENT_LOG_NAME))
FILE_HANDLER.setLevel(logging.DEBUG)

# Stderr Handler
STREAM_HANDLER = logging.StreamHandler()
STREAM_HANDLER.setLevel(logging.WARNING)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
STREAM_HANDLER.setFormatter(formatter)
FILE_HANDLER.setFormatter(formatter)
