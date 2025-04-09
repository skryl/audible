from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="audible",
    version="0.1.0",
    author="Audible Team",
    author_email="",
    description="A package for generating AI audiobooks from text",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/skryl/audible",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "openai>=1.0.0",
        "tiktoken",
        "requests",
        "python-dotenv",
        "pydub",
        "cartesia",
    ],
    entry_points={
        "console_scripts": [
            "audible=audible.cli.main:main",
        ],
    },
    package_data={
        "audible": ["prompts.json"],
    },
)