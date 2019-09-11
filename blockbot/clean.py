'''
    clean
    =====

    Clean all data storage.
'''

import os

from . import collections
from . import log
from . import path


def clean_logs():
    '''Clean existing logs.'''

    for file in os.listdir(path.log_dir()):
        if file.endswith(".log") and file != log.CURRENT_LOG_NAME:
            log.info(f'Cleaning log file "{file}"')
            os.remove(os.path.join(path.log_dir(), file))


def clean_tables():
    '''Clean existing WiredTiger data tables.'''

    with collections.Connection.new(path.db_dir()) as conn:
        for file in os.listdir(path.db_dir()):
            if file.endswith(".wt") and not file.startswith('WiredTiger'):
                name = file[:-3]
                if name.isalnum():
                    log.info(f'Cleaning dataset file "{file}"')
                    if conn.drop(f'table:{name}') != 0:
                        raise OSError


def clean_all():
    '''Clean all existing data.'''

    clean_logs()
    clean_tables()
