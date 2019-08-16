VALID_OPTIONS = {
    "pkg-info-file": {
        "optionnal": True,
        "description": """Pass a PKG-INFO file direcly usable.

> ! NOTE: All other keys will be ignored if you pass an already prepared `PKG-INFO`
> file
""" },

    "author": {
        "description": "Your name"
    },

    "author-email": {
        "description": """Your email address

e.g. for mesonpep517 itself:

``` toml
[tool.mesonpep517.metadata]
Author="Thibault Saunier"
Author-email="tsaunier@gnome.org"
```"""
    },

    "summary": {
         "description": "A one sentence summary about the package"
    },

    "meson-python-option-name": {
        "optionnal": True,
        "description": """The name of the meson options that is used in the meson build definition
to set the python installation when using
[`python.find_installation()`](http://mesonbuild.com/Python-module.html#find_installation)."""
    },

    "meson-options": {
        "optionnal": True,
        "description": """A list of default meson options to set, can be overriden and expended through the `MESON_ARGS`
environement variable at build time."""
    },

    "requires": {
        "optionnal": True, 
        "description": """A list of other packages from PyPI that this package needs. Each package may
be followed by a version specifier like ``(>=4.1)`` or ``>=4.1``, and/or an
[environment marker](https://www.python.org/dev/peps/pep-0345/#environment-markers)
after a semicolon. For example:

``` toml
      requires = [
          "requests >=2.6",
          "configparser; python_version == '2.7'",
      ]
```"""
    },

    "description-file": {
        "optionnal": True,
        "description": """A path (relative to the .toml file) to a file containing a longer description
of your package to show on PyPI. This should be written in reStructuredText
  Markdown or plain text, and the filename should have the appropriate extension
  (`.rst`, `.md` or `.txt`)."""
    },

    "classifiers": {
        "optionnal": True,
        "description": "A list of [classifiers](https://pypi.python.org/pypi?%3Aaction=list_classifiers)."
    },

    "requires-python": {
        "optionnal": True,
        "description": """A version specifier for the versions of Python this requires, e.g. ``~=3.3`` or
``>=3.3,<4`` which are equivalents."""
    },

    "project_urls": {
        "optionnal": True,
        "description": """A list of `Type, url` as described in the
[pep345](https://www.python.org/dev/peps/pep-0345/#project-url-multiple-use).
For example:

``` toml
project_urls = [
    "Source, https://gitlab.com/thiblahute/mesonpep517",
]
```"""
    },

    "home-page": {
        "optionnal": True,
        "description": """A string containing the URL for the package's home page.

Example:

`http://www.example.com/~cschultz/bvote/`"""
    },

    "platforms": {
        "optionnal": True,
        "description": "Supported python platforms, can be 'any', py3, etc..."
    },

    "module": {
        "optionnal": True,
        "description": "The name of the module, will use the meson project name if not specified"
    },
}
