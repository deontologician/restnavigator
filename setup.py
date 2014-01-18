from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import sys


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


setup(
    name="rest_navigator",
    version="0.1.1",
    author="Josh Kuhn",
    author_email="deontologician@gmail.com",
    license="MIT",
    packages=find_packages(),
    url="https://www.github.com/deontologician/rest_navigator",
    install_requires=["requests>=1.1.0, <=2.2.0",
                      "uritemplate>=0.6.0",
                      "Unidecode>=0.04.14",
                      ],
    tests_require=[
        "httpretty==0.6.0",
        "pytest>=2.3.5, <=2.5.1",
    ],
    cmdclass={'test': PyTest},
)
