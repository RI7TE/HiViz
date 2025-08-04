from setuptools import setup

setup(
    name='HiViz',
    version='0.1.0',
    author='Steven Kellum',
    author_email='sk@perfectatrifecta.com',
    description=None,
    download_url='https://github.com/RI7TE/HiViz.git',
    license="'Proprietary License'",
    packages=[],
    py_modules=['hiviz'],
    python_requires=">={}.{}".format(3, 13),
    install_requires=['colorama==0.4.6'],
    
)
