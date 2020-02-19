'''
    daemonize
    =========

    Daemonize long-standing requests.

    # Warning

    Do not have multiple daemons running at the same time.
'''

import daemonize
import gc
import os
import requests
import signal
import tempfile
import time
import tweepy

from . import api
from . import collections
from . import log

# Logger for BlockFollowers.
LOGGER = log.new_logger('Daemon')
# Unique name for application.
APP_NAME = 'blockbot_daemon'
# File descriptions for files we need to keep open (logger).
KEEP_FDS = [
    log.FILE_HANDLER.stream.fileno(),
]

def get_pid(name):
    '''Get the process ID file for the daemon.'''

    return os.path.join(tempfile.gettempdir(), f'blockbot-{name}.pid')


def close_wiredtiger_connections():
    '''Close all open connections to WiredTiger.'''

    # Ensure we don't have any accidentally closed PIDs.
    for connection in collections.CONNECTIONS.values():
        connection.close()


def handle_connection_error():
    '''Garbage collect and sleep on connection errors.'''

    # Make sure we collect available resources to try to
    # avoid memory leaks.
    gc.collect()
    # Sleep for 10 minutes, then we can re-try.
    LOGGER.info('Non-critical connection error occurred, sleeping for 10 minutes.')
    time.sleep(600)


def as_daemon(method, name, *args, **kwds):
    '''Run long-standing process as daemon.'''

    def main():
        '''Wrapper for the method. Handles connection loss and other errors.'''

        while True:
            try:
                # If the method completes, break. Otherwise,
                # just exit.
                method(*args, **kwds)
                break
            except tweepy.TweepError as error:
                LOGGER.error(error.reason)
                if api.is_connection_error(error):
                    handle_connection_error()
                else:
                    raise
            except requests.exceptions.RequestException as error:
                LOGGER.error(str(error))
                handle_connection_error()
            except Exception as error:
                LOGGER.critical(str(error))
                raise

    close_wiredtiger_connections()
    pid = get_pid(name)
    daemon = daemonize.Daemonize(app=APP_NAME, pid=pid, action=main, keep_fds=KEEP_FDS)
    daemon.start()

def close_daemon(name):
    '''Close the long-running daemon from the PID.'''

    pid_file = get_pid(name)
    with open(pid_file) as f:
        pid = int(f.read())
    os.kill(pid, signal.SIGTERM)
