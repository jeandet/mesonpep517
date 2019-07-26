project(
    'mesonpep517',
    version : '0.1.96',
    license: 'LGPL2+',
    metadata: {'python-metadata': {
            'summary': 'Create pep517 compliant builds from the meson build system',
            'author': 'Thibault Saunier',
            'author-email': 'tsaunier@gnome.org',
            'home-page': 'https://gitlab.com/thiblahute/mesonpep517',
            'requires': [
                'wheel',
                'meson',
            ],
            'description-file': 'README.md',
            'classifiers ':  [
                'Intended Audience :: Developers',
                'License :: OSI Approved :: LGPL2+ License',
                'Programming Language :: Python :: 3',
                'Topic :: Software Development :: Libraries :: Python Modules',
            ],
            'requires_dist ':  ['wheel', 'meson', 'pytoml',],
            'entry_points': {
                'console_scripts': [
                    'otioview = opentimelineview.console:main',
                    'otiocat = opentimelineio.console.otiocat:main',
                    'otioconvert = opentimelineio.console.otioconvert:main',
                    'otiostat = opentimelineio.console.otiostat:main',
                    'otioautogen_serialized_schema_docs = opentimelineio.console.autogen_serialized_datamodel:main',
                ]
            }
        }
    },
)

python = import('python').find_installation()
subdir('mesonpep517')
