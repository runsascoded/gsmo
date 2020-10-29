from utz.setup import setup

setup(
    install_requires=[
        'utz[setup]==0.0.25',
    ],
    url="https://github.com/runsascoded/gsmo",
    entry_points={
        'console_scripts': [
            'gsmo = gsmo.gsmo:main',
            'gsmo-entrypoint = gsmo.run:main',
        ],
    },
    python_requires='>3.8',  # uses the walrus operator
)
