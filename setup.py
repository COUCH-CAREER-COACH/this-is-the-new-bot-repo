"""Setup file for arbitrage-bot package"""
from setuptools import setup, find_packages

setup(
    name="arbitrage-bot",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "web3>=6.0.0",
        "eth-abi>=4.0.0",
        "eth-utils>=2.0.0",
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "matplotlib>=3.0.0",
        "numpy>=1.20.0",
        "psutil>=5.8.0",
        "aiohttp>=3.8.0",
        "python-dotenv>=0.19.0",
    ],
    extras_require={
        'dev': [
            'pytest',
            'pytest-asyncio',
            'pytest-cov',
            'black',
            'isort',
            'mypy',
            'pylint'
        ]
    },
    python_requires='>=3.8',
    author="Your Name",
    author_email="your.email@example.com",
    description="MEV arbitrage bot with sandwich, frontrun, and JIT liquidity strategies",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/arbitrage-bot",
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
    ],
)
