from setuptools import setup, find_namespace_packages


setup(
    name='mama-demo',
    version='0.5.0',
    author="Dirk Makowski",
    author_email="dirk.makowski@gmail.com",
    description="Command-line application to demo the features of mama",
    long_description_content_type="text/markdown",
    url="https://parenchym.com",
    packages=find_namespace_packages(include=['mama_demo.*']),
    entry_points={
        'console_scripts': [
            'mama-demo = mama_demo.__main__:main'
        ],
        'gui_scripts': []
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
    ],
)
