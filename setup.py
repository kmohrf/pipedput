import os

from setuptools import find_packages, setup

__dir = os.path.abspath(os.path.dirname(__file__))
__version__ = "2.7.1"

try:
    with open(os.path.join(__dir, "README.md"), encoding="utf-8") as f:
        long_description = "\n" + f.read()
except FileNotFoundError:
    long_description = ""


setup(
    name="pipedput",
    version=__version__,
    description="A general-purpose GitLab pipeline artifact handler",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kmohrf/pipedput",
    author="Konrad Mohrfeldt",
    author_email="konrad.mohrfeldt@farbdev.org",
    packages=find_packages(),
    include_package_data=True,
    license="AGPLv3+",
    classifiers=[
        "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Development Status :: 4 - Beta",
    ],
    install_requires=[
        "flask>=1.1.2,<3.0.0",
        "flask-mail<1.0.0",
        "html2text",
        "jinja2",
    ],
    package_data={"": ["README.md"]},
)
