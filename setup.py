from setuptools import setup

setup(
    name='kiss',
    version='0.1',
    py_modules=['kiss'],
    install_requires=[
        'click==4.0', 'requests==2.5.3'
    ],
    entry_points='''[console_scripts]
kiss=kiss:cli'''
)