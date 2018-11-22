import os
from setuptools import setup, find_packages
from pipedput import VERSION

__dir = os.path.abspath(os.path.dirname(__file__))

try:
    with open(os.path.join(__dir, 'README.md'), encoding='utf-8') as f:
        long_description = '\n' + f.read()
except FileNotFoundError:
    long_description = ''


setup(
    name='pipedput',
    version=VERSION,
    description='a GitLab Pipeline Hook to dput web service',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/kmohrf/pipedput',
    author='Konrad Mohrfeldt',
    author_email='konrad.mohrfeldt@farbdev.org',
    packages=find_packages(),
    include_package_data=True,
    license='AGPLv3+',
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Development Status :: 4 - Beta',
    ],
    install_requires=['flask'],
    package_data={
        '': {'README.md'}
    }
)
