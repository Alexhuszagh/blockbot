'''
    path
    ====

    High-level path utilities relative to project.
'''

import os


def project_dir():
    '''Get the directory to the project folder.'''

    path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    if 'site-packages' in path:
        return os.path.join(os.path.expanduser('~'), '.blockbot')
    return path

def config_dir():
    '''Get the directory to the config folder.'''
    return os.path.join(project_dir(), 'config')

def db_dir():
    '''Get the directory to the db folder.'''
    return os.path.join(project_dir(), 'db')

def db_path():
    '''Get the filename to the SQLite database.'''
    return os.path.join(db_dir(), 'database.sqlite')

def log_dir():
    '''Get the directory to the log folder.'''
    return os.path.join(project_dir(), 'log')
