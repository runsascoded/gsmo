from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="gsmo",
    version="0.0.1",
    author="Ryan Williams",
    author_email="ryan@runsascoded.com",
    description="Workflow/Module system integrating Git and Docker; build Jupyter notebooks in a container, integrate changes with Git, and check notebook runs into Git",
    install_requires=[],
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/runsascoded/gismo",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
