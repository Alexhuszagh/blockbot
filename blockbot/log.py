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


LOGGER = logging.getLogger('blockbot')
LOGGER.setLevel(logging.DEBUG)
CURRENT_LOG_NAME = log_name()

# File Handler
FH = logging.FileHandler(os.path.join(path.log_dir(), CURRENT_LOG_NAME))
FH.setLevel(logging.DEBUG)

# Stderr Handler
SH = logging.StreamHandler()
SH.setLevel(logging.WARNING)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
SH.setFormatter(formatter)
FH.setFormatter(formatter)

# Add the handlers to logger
LOGGER.addHandler(SH)
LOGGER.addHandler(FH)


def debug(msg, *args, **kwds):
    LOGGER.debug(msg, *args, **kwds)


def info(msg, *args, **kwds):
    LOGGER.info(msg, *args, **kwds)


def warning(msg, *args, **kwds):
    LOGGER.warning(msg, *args, **kwds)


def error(msg, *args, **kwds):
    LOGGER.error(msg, *args, **kwds)


def critical(msg, *args, **kwds):
    LOGGER.critical(msg, *args, **kwds)
