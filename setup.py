#!/usr/bin/python
try:
    from setuptools import setup
except ImportError:
    import distribute_setup
    distribute_setup.use_setuptools()
    from setuptools import setup

setup(
    name='renode-run',
    version='0.1.0',
    author='Antmicro',
    description="Download and run Renode without thinking about it",
    author_email='contact@antmicro.com',
    url='antmicro.com',
    packages=['renode_run'],
    install_requires=[
        'dts2repl @ git+https://github.com/antmicro/dts2repl@main#egg=dts2repl',
    ],
    entry_points={
        'console_scripts': [
            'renode-run=renode_run.__main__:main',
        ]},
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Utilities',
    ],
)
