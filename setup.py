from utz.setup import setup

setup(
    install_requires=[
        'pyyaml',
        'utz[setup]>=0.0.36',
    ],
    extras_require={
        'test': [
            'GitPython',
            'pytest==6.0.1',
        ],
    },
    url="https://github.com/runsascoded/gsmo",
    entry_points={
        'console_scripts': [
            'gsmo = gsmo.gsmo:main',
            'gsmo-entrypoint = gsmo.entrypoint:main',
        ],
    },
    python_requires='>3.8',  # uses the walrus operator
)
