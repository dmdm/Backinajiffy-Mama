from pathlib import Path
from setuptools import setup, find_namespace_packages
import sys
sys.path = [Path(__file__).parent] + sys.path
from backinajiffy.mama.const import PROJECT_NAME, PROJECT_VERSION


# noinspection DuplicatedCode
def read_file(fn: str, as_lines=False) -> str:
    with open(fn, 'rt', encoding='utf-8') as fp:
        return fp.readlines() if as_lines else fp.read()

setup(
    name=PROJECT_NAME,
    version=PROJECT_VERSION,
    author="Dirk Makowski",
    author_email="dirk.makowski@gmail.com",
    description="Library to build CLI tools",
    long_description=read_file('README.md'),
    long_description_content_type="text/markdown",
    url="https://parenchym.com",
    packages=find_namespace_packages(include=['backinajiffy.*']),
    entry_points={
        'console_scripts': [],
        'gui_scripts': []
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
    ],
    install_requires=read_file('requirements.txt')
)
