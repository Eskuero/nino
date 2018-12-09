import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name = 'syncall',
    version = '1.0',
    author='Óliver García Albertos',
    author_email='3skuero@gmail.com',
    description = 'Command line script to automatize syncing, building and signing of open source Android apps using gradle',
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages = ['syncall'],
    entry_points = {
        'console_scripts': [
            'syncall=syncall:main'
        ]
    },
    install_requires = [
        'toml'
    ],
    project_urls = {
        'Documentation': 'https://github.com/Eskuero/syncall/blob/master/README.md',
        'Source': 'https://github.com/Eskuero/syncall'
    },
    classifiers = [
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
        'Topic :: System :: Software Distribution',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Software Development :: Version Control :: Git'
    ]
)
