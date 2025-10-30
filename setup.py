from setuptools import setup, find_packages

setup(
    name='binance-trading-bot',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'python-binance==1.0.19',
        'python-dotenv==1.0.0',
        'rich==13.7.0',
        'pandas==2.1.4',
        'numpy==1.26.2',
        'requests==2.31.0',
        'websocket-client==1.7.0',
        'colorlog==6.8.0',
        'tabulate==0.9.0',
        'click==8.1.7', # Optional, if using click for CLI
    ],
    extras_require={
        'dev': [
            'pytest==7.4.3',
            'pytest-asyncio==0.23.2',
            'pytest-cov==4.1.0',
        ]
    },
    entry_points={
        'console_scripts': [
            'binance-bot=src.main:main',
        ],
    },
    author='[Your Name]',
    author_email='your.email@example.com',
    description='A professional-grade Binance Futures trading bot.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/yourprofile/binance-trading-bot', # Replace with your repo URL
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Intended Audience :: Financial and Insurance Industry',
        'Topic :: Office/Business :: Financial :: Investment',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    python_requires='>=3.8',
)