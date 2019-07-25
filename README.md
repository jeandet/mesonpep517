# mesonpep517

This is a simple module that implements pep517 for the [meson] build system.

This means that you only need to provide a `pyproject.toml` in your project
source root to be able to publish your project built with meson on PyPi
and to create a wheel for the project.

The simplest `pyproject.toml` file looks like:

``` toml
[build-system]
requires = ["mesonpep517", "wheel", "meson"]
build-backend = "mesonpep517.buildapi"

[tool.mesonpep517]
build-backend = "mesonpep517.buildapi"
```

[meson]: https://mesonbuild.com