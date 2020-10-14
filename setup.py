from utz.setup import setup

setup(
    version="0.0.1",
    install_requires=[
        'utz==0.0.17',
    ],
    url="https://github.com/runsascoded/gsmo",
    entry_points={
        'console_scripts': [
            'gsmo = gsmo.gsmo:main',
        ],
    },
)
