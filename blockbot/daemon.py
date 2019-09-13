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
import tempfile
import time
import tweepy

from . import api
from . import collections
from . import log

# Logger for BlockFollowers.
LOGGER = log.new_logger('Daemon')
# Process ID
PID = os.path.join(tempfile.gettempdir(), 'blockbot.pid')
# Unique name for application.
APP_NAME = 'blockbot_daemon'
# File descriptions for files we need to keep open (logger).
KEEP_FDS = [
    log.FILE_HANDLER.stream.fileno(),
]

def close_wiredtiger_connections():
    '''Close all open connections to WiredTiger.'''

    # Ensure we don't have any accidentally closed PIDs.
    for connection in collections.CONNECTIONS.values():
        connection.close()


def as_daemon(method, *args, **kwds):
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
                # Make sure we collect available resources to try to
                # avoid memory leaks.
                gc.collect()
                LOGGER.error(error.reason)
                if api.is_connection_error(error):
                    # Sleep for 10 minutes and re-try.
                    time.sleep(600)
                else:
                    raise

    close_wiredtiger_connections()
    daemon = daemonize.Daemonize(app=APP_NAME, pid=PID, action=main, keep_fds=KEEP_FDS)
    daemon.start()
