import platform

from setuptools import setup


setup(
    name='HiViz',
    version='0.1.0',
    author='Steven Kellum',
    author_email='sk@perfectatrifecta.com',
    description='High Visibility - A Python library for creating colorful logging and debugging output',
    download_url='https://github.com/RI7TE/HiViz.git',
    license="'Proprietary License'",
    packages=[],
    py_modules=['hiviz', '_glasses'],
    python_requires=f">={platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}",
    install_requires=['colorama==0.4.6'],
)
