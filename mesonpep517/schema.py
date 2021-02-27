VALID_OPTIONS = {
    "author": {
        "description": "Your name"
    },

    "author-email": {
        "description": """Your email address

e.g. for mesonpep517 itself:

``` toml
[tool.mesonpep517.metadata]
author="Thibault Saunier"
author-email="tsaunier@gnome.org"
```"""
    },

    "classifiers": {
        "description": "A list of [classifiers](https://pypi.python.org/pypi?%3Aaction=list_classifiers)."
    },

    "description": {
        "description": "The description of the project as a string if you do not want to specify 'description-file'"
    },

    "description-file": {
        "description": """A path (relative to the .toml file) to a file containing a longer description
of your package to show on PyPI. This should be written in reStructuredText
  Markdown or plain text, and the filename should have the appropriate extension
  (`.rst`, `.md` or `.txt`)."""
    },

    "home-page": {
        "description": """A string containing the URL for the package's home page.

Example:

`http://www.example.com/~cschultz/bvote/`"""
    },

    "license": {
        "description": """Text indicating the license covering the distribution. This text can be either a valid license expression as defined in [pep639](https://www.python.org/dev/peps/pep-0639/#id88) or any free text."""
    },

    "maintainer": {
        "description": "Name of current maintainer of the project (if different from author)"
    },

    "maintainer-email": {
        "description": """Maintainer email address

Example:

``` toml
[tool.mesonpep517.metadata]
maintainer="Robin Goode"
maintainer-email="rgoode@example.org"
```"""
    },

    "meson-options": {
        "description": """A list of default meson options to set, can be overriden and expended through the `MESON_ARGS`
environement variable at build time."""
    },

    "meson-python-option-name": {
        "description": """The name of the meson options that is used in the meson build definition
to set the python installation when using
[`python.find_installation()`](http://mesonbuild.com/Python-module.html#find_installation)."""
    },

    "module": {
        "description": "The name of the module, will use the meson project name if not specified"
    },

    "pkg-info-file": {
        "description": """Pass a PKG-INFO file direcly usable.

> ! NOTE: All other keys will be ignored if you pass an already prepared `PKG-INFO`
> file
"""
    },

    "platforms": {
        "description": "Supported Python platforms, can be 'any', py3, etc..."
    },

    "project-urls": {
        "description": """A list of `Type, url` as described in the
[pep345](https://www.python.org/dev/peps/pep-0345/#project-url-multiple-use).
For example:

``` toml
project-urls = [
    "Source, https://gitlab.com/thiblahute/mesonpep517",
]
```"""
    },

    "requires": {
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

    "requires-python": {
        "description": """A version specifier for the versions of Python this requires, e.g. ``~=3.3`` or
``>=3.3,<4`` which are equivalents."""
    },

    "summary": {
        "required": True,
        "description": "A one sentence summary about the package"
    },

}
