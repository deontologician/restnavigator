from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import sys


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = ['--strict', '--verbose', '--tb=long', 'tests']
        self.test_suite = True

    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


setup(
    name="restnavigator",
    version="0.2.1",
    author="Josh Kuhn",
    author_email="deontologician@gmail.com",
    description='A python library for interacting with HAL+JSON APIs',
    url='https://github.com/deontologician/rest_navigator',
    download='https://github.com/deontologician/rest_navigator/tarball/v0.2',
    license="MIT",
    packages=['restnavigator'],
    keywords=['REST', 'HAL', 'json', 'http'],
    install_requires=["requests>=2.5.0",
                      "uritemplate>=0.6.0",
                      "Unidecode>=0.04.14",
                      ],
    tests_require=[
        "httpretty==0.6.0",
        "pytest>=2.3.5, <2.6",
    ],
    cmdclass={'test': PyTest},
)
