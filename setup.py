"""
Setup script for PaddockPulse.
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="paddockpulse",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A comprehensive social media management platform for the racing industry",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/paddockpulse",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "paddockpulse=paddock_pulse.main:main",
            "paddockpulse-init-db=paddock_pulse.scripts.init_db:main",
        ],
    },
) 