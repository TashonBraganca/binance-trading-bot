
from setuptools import setup, find_packages

setup(
    name="binance_trading_bot",
    version="2.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A professional-grade Binance Futures trading bot.",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourprofile/binance-trading-bot",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=open('requirements.txt').read().splitlines(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.9',
    entry_points={
        'console_scripts': [
            'trading-bot=main:main',
        ],
    },
)
