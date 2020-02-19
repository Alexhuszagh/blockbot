'''
    kill_block_media_replies
    ========================

    Stop the `block_media_replies` daemon.
'''

try:
    import blockbot
except ImportError:
    # Script probably not installed, in scripts directory.
    import sys
    project_home = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    sys.path.insert(0, project_home)
    import blockbot


def main():
    blockbot.close_daemon('block_media_replies')


if __name__ == '__main__':
    main()
