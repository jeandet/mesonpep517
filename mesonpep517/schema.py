VALID_OPTIONS = {
    # In [project]
    "name": {
        "description":
        """The name of the project, as a string.
The name specified in `project()` in the `meson.build` file will be used in case this is not specified.\n."""
        'See: https://www.python.org/dev/peps/pep-0621/#name'
    },

    "authors": {
        "description":
        'An array of tables with 2 keys: name and email.\n'
        'See: https://www.python.org/dev/peps/pep-0621/#authors-maintainers'
    },

    "maintainers": {
        "description":
        'An array of tables with 2 keys: name and email.\n'
        'See: https://www.python.org/dev/peps/pep-0621/#authors-maintainers'
    },

    "description": {
        "description": "A one sentence summary about the package\n"
        "See: https://www.python.org/dev/peps/pep-0621/#description"
    },

    "readme": {
        "description":
        'The full description of the project (i.e. the README).\n'
        'See: https://www.python.org/dev/peps/pep-0621/#readme',
    },

    "dependencies": {
        "description": """A list of other packages from PyPI that this package needs. Each package may
be followed by a version specifier like ``(>=4.1)`` or ``>=4.1``, and/or an
[environment marker](https://www.python.org/dev/peps/pep-0345/#environment-markers)
after a semicolon. For example:

``` toml
      dependencies = [
          "requests >=2.6",
          "configparser; python_version == '2.7'",
      ]
```"""
    },

    "optional-dependencies": {
        'description': 'A list of other optional packages from PyPI that this '
        'package may use.\n'
        'See: https://www.python.org/dev/peps/pep-0621/#dependencies-optional-dependencies'
    },

    'urls': {

        'description': 'A table of URLs where the key is the URL label and the value is the URL itself.\n'
        'See: https://www.python.org/dev/peps/pep-0621/#urls'
    },

    "dynamic": {
        "description":
        'An array of strings, Specifies which fields listed by this PEP were '
        'intentionally unspecified so another tool can/will provide such '
        'metadata dynamically.\n'
        'See: https://www.python.org/dev/peps/pep-0621/#dynamic'
    },


    # From [tool.mesonpep517.metadata]
    "author": {
        "deprecated-by": "project.authors",
        "description": "Your name"
    },

    "author-email": {
        "deprecated-by": "project.authors",
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

    "description-file": {
        "deprecated-by": "project.readme",
        "description": """A path (relative to the .toml file) to a file containing a longer description
of your package to show on PyPI. This should be written in reStructuredText
  Markdown or plain text, and the filename should have the appropriate extension
  (`.rst`, `.md` or `.txt`)."""
    },

    "home-page": {
        "deprecated-by": "project.urls.homepage",
        "description": """A string containing the URL for the package's home page.

Example:

`http://www.example.com/~cschultz/bvote/`"""
    },

    "license": {
        "deprecated-by": "project.license",
        "description":
        "A table with either a `text` key and value of the license text or"
        " a `file` key and value being a relative path to the license file.\n"
        "See: https://www.python.org/dev/peps/pep-0621/#license"
    },

    "maintainer": {
        "deprecated-by": "project.maintainers",
        "description": "Name of current maintainer of the project (if different from author)"
    },

    "maintainer-email": {
        "deprecated-by": "project.maintainers",
        "description": """Maintainer email address

Example:

``` toml
[tool.mesonpep517.metadata]
maintainer="Robin Goode"
maintainer-email="rgoode@example.org"
```"""
    },

    "meson-options": {
        "description": """A list of default meson options to set, can be overridden and expended through the use of
[`config_settings`](https://www.python.org/dev/peps/pep-0517/#build-backend-interface).

`mesonpep517` supports the following `config_settings`:

- `--setup-args`: arguments that get passed along to the `meson setup` command at the end

```sh
python3 -m build . --config-setting=--setup-args="-Doption=value -Dother-option=value"

# translates to
meson setup ... -Doption=value -Dother-option=value
```

- `--dist-args`: arguments that get passed along to the `meson dist` command at the end

```sh
python3 -m build . --config-setting=--dist-args="--formats gztar --no-tests"
# translates to
meson dist ... --formats gztar --no-tests
```

- `--install-args`: arguments that get passed along to the `meson install` command at the end

```sh
python3 -m build . --config-setting=--install-args="--no-rebuild"
# translates to
meson install ... --no-rebuild
```"""
    },

    "meson-python-option-name": {
        "description": """The name of the meson options that is used in the meson build definition
to set the python installation when using
[`python.find_installation()`](http://mesonbuild.com/Python-module.html#find_installation)."""
    },

    "module": {
        "deprecated-by": "project.maintainers",
        "description": "The name of the module, will use the meson project name if not specified"
    },

    "pkg-info-file": {
        "description": """Pass a PKG-INFO file directly usable.

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
        "deprecated-by": "project.dependencies",
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
        "deprecated-by": "project.description",
        "description": "A one sentence summary about the package"
    },

}
