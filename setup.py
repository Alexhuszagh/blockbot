import os
import setuptools
import subprocess
import sys


def shell_command(command, short_description):
    """Create a simple command that is invoked using subprocess."""

    class ShellCommand(setuptools.Command):
        """Run custom script when invoked."""

        description = short_description
        user_options = []

        def initialize_options(self):
            pass

        def finalize_options(self):
            pass

        def run(self):
            subprocess.call(command)

    return ShellCommand


def unittest_command(suite):
    """Get new command for unittest suite."""

    return [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-v",
        "-s",
        suite,
        "-p",
        "*_test.py"
    ]

LICENSE = "Apache-2.0"
MAINTAINER = ['Alex Huszagh']
MAINTAINER_EMAIL = ['ahuszagh@gmail.com']
NAME = "blockbot"
URL = "https://github.com/Alexhuszagh/blockbot.git"
VERSION = "0.0.1"

DESCRIPTION = "Automated utilities to block users on Twitter."
LONG_DESCRIPTION = """Sick of seeing fancams?
Dogpiled by followers of a certain user?
Blockbot has you covered: an open-source, scalable solution to help fix Twitter.
"""

PACKAGES = setuptools.find_packages()
HOME = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(HOME, 'requirements.txt')) as f:
    REQUIRES = f.read().splitlines()

SCRIPTS = [os.path.join('scripts', i) for i in os.listdir('scripts')]
COMMANDS = {
    'test': shell_command(
        command=unittest_command("tests"),
        short_description="Run unittest suite."
    ),
}

# Writeable configuration files to install.
DATA_FILES = [
    (os.path.join(os.path.expanduser('~'), '.blockbot', 'config'), [
        'config/api.json',
        'config/block_followers.json',
        'config/block_media_replies.json',
    ]),
]

setuptools.setup(
    install_requires=REQUIRES,
    python_requires=">=3.7",
    scripts=SCRIPTS,
    data_files=DATA_FILES,
    packages=PACKAGES,
    cmdclass=COMMANDS,
    zip_safe=False,
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    maintainer=MAINTAINER,
    maintainer_email=MAINTAINER_EMAIL,
    url=URL,
    license=LICENSE,
)
