'''
    blockbot_to_csv
    ===============

    Dump databases to CSV.
'''

import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument(
    '-o',
    '--output-directory',
    dest='output',
    help='Output directory to store files.',
    required=True
)
args = parser.parse_args()

try:
    import blockbot
except ImportError:
    # Script probably not installed, in scripts directory.
    import sys
    project_home = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    sys.path.insert(0, project_home)
    import blockbot


def main():
    databases = blockbot.get_databases()
    os.makedirs(args.output, exist_ok=True)
    for module, module_databases in databases.items():
        directory = os.path.join(args.output, module)
        os.makedirs(directory, exist_ok=True)
        for name, database in module_databases.items():
            path = os.path.join(directory, f'{name}.csv')
            database.to_csv(path)

if __name__ == '__main__':
    main()
