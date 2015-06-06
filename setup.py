from setuptools import setup

setup(
    name='kiss',
    version='0.1',
    py_modules=['kiss'],
    install_requires=[
        'Click',
    ],
    entry_points='''[console_scripts]
kiss=kiss:cli'''
)