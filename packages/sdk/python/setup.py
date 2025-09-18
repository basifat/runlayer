"""
Setup script for RunLayer Python SDK
"""

from setuptools import setup, find_packages

# Read long description from README
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="runlayer",
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    author="RunLayer Team",
    author_email="sdk@runlayer.com",
    description="RunLayer Python SDK - Temporal for AI Validation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/runlayer/runlayer",
    project_urls={
        "Bug Tracker": "https://github.com/runlayer/runlayer/issues",
        "Documentation": "https://docs.runlayer.com/sdk/python",
        "Source Code": "https://github.com/runlayer/runlayer",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Security :: Cryptography",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pydantic>=2.0.0,<3.0.0",
        "httpx>=0.25.0,<1.0.0",
        "cryptography>=41.0.0,<42.0.0",
        "structlog>=23.0.0,<24.0.0",
        "click>=8.0.0,<9.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.5.0",
            "pre-commit>=3.0.0",
        ],
        "docs": [
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.0.0",
            "mkdocstrings[python]>=0.22.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "runlayer=runlayer.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
