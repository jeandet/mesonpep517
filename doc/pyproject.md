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

### `name`

The name of the project, as a string.
The name specified in `project()` in the `meson.build` file will be used in case this is not specified.
.See: https://www.python.org/dev/peps/pep-0621/#name

### `authors`

An array of tables with 2 keys: name and email.
See: https://www.python.org/dev/peps/pep-0621/#authors-maintainers

### `maintainers`

An array of tables with 2 keys: name and email.
See: https://www.python.org/dev/peps/pep-0621/#authors-maintainers

### `description`

A one sentence summary about the package
See: https://www.python.org/dev/peps/pep-0621/#description

### `readme`

The full description of the project (i.e. the README).
See: https://www.python.org/dev/peps/pep-0621/#readme

### `dependencies`

A list of other packages from PyPI that this package needs. Each package may
be followed by a version specifier like ``(>=4.1)`` or ``>=4.1``, and/or an
[environment marker](https://www.python.org/dev/peps/pep-0345/#environment-markers)
after a semicolon. For example:

``` toml
      dependencies = [
          "requests >=2.6",
          "configparser; python_version == '2.7'",
      ]
```

### `optional-dependencies`

A list of other optional packages from PyPI that this package may use.
See: https://www.python.org/dev/peps/pep-0621/#dependencies-optional-dependencies

### `urls`

A table of URLs where the key is the URL label and the value is the URL itself.
See: https://www.python.org/dev/peps/pep-0621/#urls

### `dynamic`

An array of strings, Specifies which fields listed by this PEP were intentionally unspecified so another tool can/will provide such metadata dynamically.
See: https://www.python.org/dev/peps/pep-0621/#dynamic

### `author` (Deprecated, use `project.authors` instead)

Your name

### `author-email` (Deprecated, use `project.authors` instead)

Your email address

e.g. for mesonpep517 itself:

``` toml
[tool.mesonpep517.metadata]
author="Thibault Saunier"
author-email="tsaunier@gnome.org"
```

### `classifiers`

A list of [classifiers](https://pypi.python.org/pypi?%3Aaction=list_classifiers).

### `description-file` (Deprecated, use `project.readme` instead)

A path (relative to the .toml file) to a file containing a longer description
of your package to show on PyPI. This should be written in reStructuredText
  Markdown or plain text, and the filename should have the appropriate extension
  (`.rst`, `.md` or `.txt`).

### `home-page` (Deprecated, use `project.urls.homepage` instead)

A string containing the URL for the package's home page.

Example:

`http://www.example.com/~cschultz/bvote/`

### `license` (Deprecated, use `project.license` instead)

Text indicating the license covering the distribution. This text can be either a valid license expression as defined in [pep639](https://www.python.org/dev/peps/pep-0639/#id88) or any free text.

### `maintainer` (Deprecated, use `project.maintainers` instead)

Name of current maintainer of the project (if different from author)

### `maintainer-email` (Deprecated, use `project.maintainers` instead)

Maintainer email address

Example:

``` toml
[tool.mesonpep517.metadata]
maintainer="Robin Goode"
maintainer-email="rgoode@example.org"
```

### `meson-options`

A list of default meson options to set, can be overridden and expended through the use of
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
```

### `meson-python-option-name`

The name of the meson options that is used in the meson build definition
to set the python installation when using
[`python.find_installation()`](http://mesonbuild.com/Python-module.html#find_installation).

### `module` (Deprecated, use `project.maintainers` instead)

The name of the module, will use the meson project name if not specified

### `pkg-info-file`

Pass a PKG-INFO file directly usable.

> ! NOTE: All other keys will be ignored if you pass an already prepared `PKG-INFO`
> file


### `platforms`

Supported Python platforms, can be 'any', py3, etc...

### `project-urls`

A list of `Type, url` as described in the
[pep345](https://www.python.org/dev/peps/pep-0345/#project-url-multiple-use).
For example:

``` toml
project-urls = [
    "Source, https://gitlab.com/thiblahute/mesonpep517",
]
```

### `requires` (Deprecated, use `project.dependencies` instead)

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

### `requires-python`

A version specifier for the versions of Python this requires, e.g. ``~=3.3`` or
``>=3.3,<4`` which are equivalents.

### `summary` (Deprecated, use `project.description` instead)

A one sentence summary about the package


## Entry points section (Optional)

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
