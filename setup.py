import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name = 'nino',
    version = '1.1',
    author='Óliver García Albertos',
    author_email='3skuero@gmail.com',
    description = 'Command line script to automatize syncing, building and signing of open source Android apps using gradle',
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages = ['nino'],
    entry_points = {
        'console_scripts': [
            'nino=nino:main'
        ]
    },
    install_requires = [
        'toml',
		'colorama'
    ],
    project_urls = {
        'Documentation': 'https://github.com/Eskuero/nino/blob/master/README.md',
        'Source': 'https://github.com/Eskuero/nino'
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
