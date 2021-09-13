'''
    clean
    =====

    Clean all data storage.
'''

import os

from . import log
from . import path

# Logger for Clean.
LOGGER = log.new_logger('Clean')


def clean_logs():
    '''Clean existing logs.'''

    for file in os.listdir(path.log_dir()):
        if file.endswith(".log") and file != log.CURRENT_LOG_NAME:
            LOGGER.info(f'Cleaning log file "{file}"')
            os.remove(os.path.join(path.log_dir(), file))


def clean_tables():
    '''Clean existing SQLite data tables.'''
    os.unlink(path.db_path())


def clean_all():
    '''Clean all existing data.'''

    clean_logs()
    clean_tables()
