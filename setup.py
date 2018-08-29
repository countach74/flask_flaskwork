from setuptools import setup
from os import path


this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='flask_flaskwork',
    description='A Flask plugin to talk with the Flaskwork Chrome extension.',
    version='0.1.12',
    license='BSD',
    author='Tim Radke',
    author_email='tim.is@self-proclaimed.ninja',
    py_modules=['flask_flaskwork'],
    zip_safe=False,
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=[
        'Flask', 'sqlalchemy', 'sqlparse'
    ]
)
