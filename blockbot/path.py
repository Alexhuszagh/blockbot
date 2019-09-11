'''
    path
    ====

    High-level path utilities relative to project.
'''

import os
import json
import tweepy


def project_dir():
    '''Get the directory to the project folder.'''
    return os.path.dirname(twitter_dir())

def twitter_dir():
    '''Get the directory to the twitter folder.'''
    return os.path.dirname(os.path.realpath(__file__))

def config_dir():
    '''Get the directory to the config folder.'''
    return os.path.join(project_dir(), 'config')

def db_dir():
    '''Get the directory to the db folder.'''
    return os.path.join(project_dir(), 'db')

def log_dir():
    '''Get the directory to the log folder.'''
    return os.path.join(project_dir(), 'log')
