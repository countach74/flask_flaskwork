from setuptools import setup


setup(
    name='flaskwork',
    version='0.1.0',
    license='BSD',
    author='Tim Radke',
    author_email='tim.is@self-proclaimed.ninja',
    py_modules=['flask_flaskwork'],
    zip_safe=False,
    install_requires=[
      'Flask', 'sqlalchemy'
    ]
)
