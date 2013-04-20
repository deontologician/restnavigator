from setuptools import setup

setup(
    name="rest_navigator",
    version="0.1",
    author="Josh Kuhn",
    author_email="deontologician@gmail.com",
    license="MIT",
    py_modules=['rest_navigator'],
    url="https://www.github.com/deontologician/rest_navigator",
    install_requires=["requests==1.1.0",
                      "uritemplate==0.5.2",
                      "httpretty==0.6.0"
                     ]
)
