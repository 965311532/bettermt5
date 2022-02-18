from setuptools import setup, find_packages
import betterMT5 as mt5

with open('./README.md' , 'r', encoding = 'utf-8') as f:
    readme = f.read()

setup(
    name='betterMT5',
    version=mt5.__version__.get('betterMT5'),
    author=mt5.__author__.get('betterMT5'),
    author_email='contact@gabrielearmento.com',
    description='A better version of the Python MetaTrader5 API',
    long_description_content_type='text/markdown',
    long_description=readme,
    packages=find_packages(where='betterMT5'),
    url='https://github.com/965311532/betterMT5',
    license=None,
    install_requires=['pymt5adapter'],
    python_requires='>=3.6'
    )