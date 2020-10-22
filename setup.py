from setuptools import setup, find_packages

from pi_relays_control import __version__

_NAME = 'pi_relays_control'

setup(
    name=_NAME,
    version=__version__,
    description='Raspberry Pi relays board control interface',
    url='https://pypi.org/simple/{}'.format(_NAME),
    author='Davy Gabard',
    author_email='davy.gabard@gmail.com',
    packages=find_packages(),
    install_requires=[
        'RPi.GPIO>=0.7',
        'flask>=1.1',
        'Werkzeug>=1.0',
        'gunicorn>=20.0',
        'Jinja2>=2.11',
        'sqlalchemy>=1.3',
        'PyMySQL>=0.10'
    ],
    include_package_data=True
)
