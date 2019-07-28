# The pyproject.toml config file

This file lives at the root of the module/package, at the same place
as the toplevel `meson.build` file.

## Build system section

This tells tools like pip to build your project with flit. It's a standard
defined by PEP 517. For any project using mesonpep517, it will look like this:

``` toml
    [build-system]
    requires = ["mesonpep517"]
    build-backend = "mesonpep517.buildapi"
```

## Metadata section

> NOTE: The project version and name are extracted from the `meson.build`
> [`project()`](http://mesonbuild.com/Reference-manual.html#project) section.

This section is called `[tool.mesonpep517.metadata]` in the file.

### `author`

Your name

### `author-email`

Your email address

e.g. for mesonpep517 itself:

``` toml
[tool.mesonpep517.metadata]
Author="Thibault Saunier"
Author-email="tsaunier@gnome.org"
```

### `summary`

A one sentence summary about the package

### `meson-python-option-name`

The name of the meson options that is used in the meson build definition
to set the python installation when using
[`python.find_installation()`](http://mesonbuild.com/Python-module.html#find_installation).

### `requires` (Optionnal)

A list of other packages from PyPI that this package needs. Each package may
be followed by a version specifier like ``(>=4.1)`` or ``>=4.1``, and/or an
[environment marker](https://www.python.org/dev/peps/pep-0345/#environment-markers)
after a semicolon. For example:

``` toml
      requires = [
          "requests >=2.6",
          "configparser; python_version == '2.7'",
      ]
```

### `description-file` (Optionnal)

A path (relative to the .toml file) to a file containing a longer description
of your package to show on PyPI. This should be written in reStructuredText
  Markdown or plain text, and the filename should have the appropriate extension
  (`.rst`, `.md` or `.txt`).

### `classifiers` (Optionnal)

A list of [classifiers](https://pypi.python.org/pypi?%3Aaction=list_classifiers).

### `requires-python` (Optionnal)

A version specifier for the versions of Python this requires, e.g. ``~=3.3`` or
``>=3.3,<4`` which are equivalents.

### `project_urls` (Optionnal)

A list of `Type, url` as described in the
[pep345](https://www.python.org/dev/peps/pep-0345/#project-url-multiple-use).
For example:

``` toml
project_urls = [
    "Source, https://gitlab.com/thiblahute/mesonpep517",
]
```

## Entry points section (Optionnal)

You can declare [entry points](http://entrypoints.readthedocs.io/en/latest/)
in the `[tools.mesonpep517.entry-points]` section. It is a list of
'entrypointname = module:funcname` strings, for example for console
scripts entry points:

``` toml
[tool.mesonpep517.entry-points]
console_scripts = [
    'otioview = opentimelineview.console:main',
    'otiocat = opentimelineio.console.otiocat:main',
    'otioconvert = opentimelineio.console.otioconvert:main',
    'otiostat = opentimelineio.console.otiostat:main',
    'otioautogen_serialized_schema_docs = opentimelineio.console.autogen_serialized_datamodel:main',
]
```
