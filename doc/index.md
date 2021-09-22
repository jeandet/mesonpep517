# The mesonpep517 module

This is a python module that implements [pep517] for the [meson] build system.

This implies that any project that deals with python code can easily distributed
to [the Python Package Index (PyPI)](https://pypi.org/) by just setting the right
metadatas in its [`pyproject.toml`] config file

[meson]: https://mesonbuild.com
[pep517]: https://www.python.org/dev/peps/pep-0517/
[`pyproject.toml`]: https://www.python.org/dev/peps/pep-0518/#file-format

## Usage

`mesonpep517` doesn't provide any command line tools and should be used
though other standard tools like [pip3](https://pip.pypa.io/en/stable/),
[twine](https://pypi.org/project/twine/) and [build](https://pypi.org/project/build/)

## Arguments

`mesonpep517` supports the following [`config_settings`](https://www.python.org/dev/peps/pep-0517/#config-settings):

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

- `--log=<LOG_LEVEL>`: Make the `mesonpep517` backend verbose, level can be:
   - `DEBUG`: Detailed information, typically of interest only when diagnosing problems.
   - `INFO`: Confirmation that things are working as expected.
   - `WARNING`: An indication that something unexpected happened, or indicative
     of some problem in the near future (e.g. ‘disk space low’). The software is
     still working as expected.
   - `ERROR`: Due to a more serious problem, the software has not been able to perform some function.
   - `CRITICAL`: A serious error, indicating that the program itself may be unable to continue running.
- `--verbose` or `-v`: Make the `mesonpep517` backend more verbose

### Workflow to upload a release to pypi

1. Add a [pyproject.toml](pyproject.md) to your project
2. Install build: `pip3 install build`
3. Build packages: `python3 -m build .` (which adds the sdist and wheel to
   the `dist/` folder)
4. Publish the package `twine upload dist/*`


In short for the next release: `rm dist/* && python3 -m build && twine upload dist/*`
