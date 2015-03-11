"""Setuptools entry point."""
from setuptools import setup
from setuptools.command.test import test as TestCommand
import sys
import os
import codecs


install_requires = [
    "requests>=2.5.0",
    "uritemplate>=0.6.0",
    "Unidecode>=0.04.14",
    "six",
]

if sys.version_info < (2, 7, 0):
    install_requires.append('ordereddict')


class Tox(TestCommand):

    """Tox test command."""

    user_options = [('tox-args=', 'a', "Arguments to pass to tox")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.tox_args = '--recreate'

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import tox
        import shlex
        errno = tox.cmdline(args=shlex.split(self.tox_args))
        sys.exit(errno)


tests_require = [
    "httpretty==0.8.4",
    "pytest==2.6.4",
    "pytest-cov==1.8.1",
    "tox",
    "pytest-cache",
],

import restnavigator

dirname = os.path.dirname(__file__)

long_description = (
    codecs.open(os.path.join(dirname, 'README.rst'), encoding='utf-8').read() + '\n' +
    codecs.open(os.path.join(dirname, 'CHANGES.rst'), encoding='utf-8').read()
)


setup(
    name="restnavigator",
    version=restnavigator.__version__,
    author="Josh Kuhn",
    author_email="deontologician@gmail.com",
    description='A python library for interacting with HAL+JSON APIs',
    long_description=long_description,
    url='https://github.com/deontologician/rest_navigator',
    license="MIT",
    packages=['restnavigator'],
    keywords=['REST', 'HAL', 'json', 'http'],
    classifiers=[
        "Development Status :: 6 - Mature",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS :: MacOS X",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3"
    ] + [("Programming Language :: Python :: %s" % x) for x in "2.6 2.7 3.0 3.1 3.2 3.3 3.4".split()],
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={
        'test': tests_require,
    },
    cmdclass={'test': Tox},
)
