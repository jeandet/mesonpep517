"""PEP-517 compliant buildsystem API"""
import contextlib
import sysconfig
import logging
import sys
import tempfile
import tarfile
import zipfile
import os
import json
import subprocess
import toml
import abc
import re
import shlex
import typing as T

from gzip import GzipFile
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version
from wheel.wheelfile import WheelFile

from .pep425tags import get_abbr_impl, get_abi_tag, get_impl_ver, get_platform_tag
from .schema import VALID_OPTIONS

log = logging.getLogger(__name__)


class Logger:
    def __init__(self, config_settings: T.Dict[str, str]):
        if hasattr(self, "config_settings"):
            return

        self.config_settings = config_settings or {}
        verbose = self.config_settings.get('--verbose')
        if verbose:
            try:
                self.verbosity = int(verbose)
            except:
                raise Exception("Invalid value for --verbose `{verbose}`, expects int.")

        if self.config_settings.get('-v'):
            self.verbosity = 0

        self.verbosity = 1

    def info(self, msg: str):
        if self.verbosity <= 0:
            return
        print(msg)

    def debug(self, msg: str):
        if self.verbosity <= 1:
            return

        print(msg)

    @staticmethod
    def warn(msg: str):
        print(f"WARN: {msg}", file=sys.stderr)

    @staticmethod
    def error(msg: str):
        print(f"ERROR: {msg}", file=sys.stderr)



class MesonCommand(abc.ABC, Logger):
    __exe = 'meson'

    def __init__(self, subcommand: str, *args: str, builddir: str, config_settings: T.Dict[str, str]=None) -> None:
        Logger.__init__(self, config_settings)

        extra_args = self.config_settings.get(f'--{subcommand}-args')
        if extra_args:
            self.args = tuple([subcommand, *args, *shlex.split(extra_args)])
        else:
            self.args = tuple([subcommand, *args])

        self.builddir = builddir

    def execute(self) -> bytes:
        try:
            env = os.environ.copy()
            # Disabling scanner cache to avoid `Invalid cross-device link`
            # renaming the cache.
            env['GI_SCANNER_DISABLE_CACHE'] = '1'
            kwargs = {
                'env': env
            }
            args = [self.__exe, *self.args]
            if self.verbosity:
                subprocess.check_call(args, **kwargs)
                return b''
            else:
                return subprocess.check_output(args, **kwargs)
        except subprocess.CalledProcessError as e:
            self.error("Could not run meson")
            if self.verbosity > 1:
                fulllog = os.path.join(self.builddir, 'meson-logs', 'meson-log.txt')
                try:
                    with open(fulllog) as f:
                        self.debug(f"Full log:\n{f.read()}")
                except:
                    self.error(f"Could not open {fulllog}")
                    pass
            raise e


class MesonSetupCommand(MesonCommand):
    """First arg must be the builddir"""
    def __init__(self, config: "Config",
                 installdir: str=None, builddir: str=None,
                 config_settings: T.Dict[str, str]=None) -> None:
        Logger.__init__(self, config_settings)

        args = self.__get_args(config, installdir, builddir)
        self.debug(f"Setup args: {args[1:]}")

        # Protect against user overriding prefix/libdir
        extra_args = self.config_settings.get("--setup-args", "")
        for arg in shlex.split(extra_args):
            if arg.startswith(("-Dprefix=", "--prefix")):
                self.error("mesonpep517 does not support overriding the prefix")
                sys.exit(1)
            elif arg.startswith(("-Dlibdir=", "--libdir")):
                self.error("mesonpep517 does not support overriding the libdir")
                sys.exit(1)

        MesonCommand.__init__(self, 'setup', *args, builddir=builddir, config_settings=config_settings)

    @staticmethod
    def __get_args(config, installdir, builddir=None):
        if config is None:
            config = Config(self.config_settings)
        res = [builddir if builddir else config.builddir] + config.get('meson-options', [])
        if installdir:
            res += ['--prefix', installdir]

        return res


class MesonDistCommand(MesonCommand):
    """First two args must be '-C' and the builddir"""

    __formats_regex = re.compile(r'[\'"]?([a-z,]+)[\'"]?')

    def __init__(self, *args: str, config_settings: T.Dict[str, str]={}) -> None:
        MesonCommand.__init__(self, 'dist', *args, '--include-subprojects',
            builddir=args[1], config_settings=config_settings)

    def formats(self) -> T.Optional[T.Tuple[str]]:
        """If formats is not passed in config_settings, defaults to ('xztar',)"""
        for i, a in enumerate(self.args):
            if a == '--formats':
                match = self.__formats_regex.match(self.args[i+1])
            elif a.startswith('--formats='):
                match = self.__formats_regex.match(a.split('=')[1])
            else:
                continue
            if not match:
                self.warn('Invalid "--formats" option. Please read Meson documentation for help.')
                return None
            group = match.groups()[0]
            if not group:
                self.warn('Invalid "--formats" option. Please read Meson documentation for help.')
                return None
            return T.cast(T.Tuple[str], group.split(','))

        return ('xztar',)

    @staticmethod
    def file_extenstion(format: str) -> str:
        if format == 'gztar':
            return '.tar.gz'
        elif format == 'xztar':
            return '.tar.xz'
        elif format == 'zip':
            return '.zip'
        else:
            assert False


class MesonInstallCommand(MesonCommand):
    """First two args must be '-C' and the builddir"""
    def __init__(self, *args: str, config_settings: T.Dict[str, str]={}) -> None:
        MesonCommand.__init__(self, 'install', *args, builddir=args[1], config_settings=config_settings)


PKG_INFO = """\
Metadata-Version: 2.1
Name: {name}
Version: {version}
"""


readme_ext_to_content_type = {
    '.rst': 'text/x-rst',
    '.md': 'text/markdown',
    '.txt': 'text/plain',
    '': 'text/plain',
}


class InstallPlan(Logger):
    def __init__(self, config: "Config", config_settings: T.Dict[str, str]):
        super().__init__(config_settings)
        self.__config = config
        try:
            self.__install_plan = config.introspect('install_plan')
            self.__installed = config.introspect('installed')
            self.__targets = {} # List of installed files for a local target

            for target in config.introspect('targets'):
                install_filenames = target.get('install_filename')
                if install_filenames:
                    for filename in target['filename']:
                        self.__targets[filename] = install_filenames
        except FileNotFoundError:
            self.__install_plan = None
            self.__installed = config.introspect('installed')

        self.is_pure = True

        self.platlibs = []
        self.distribution_files = []
        self.typelibs = []

        self.__inspect()

    def __inspect(self):
        if self.__install_plan is None:
            self.__legacy_inspect()
            return

        data_infos = {
            # Not using tags as gobject-introspection doesn't use the gnome
            # module yet to generate the typelibs.
            ".typelib": self.typelibs,
        }
        for section_data in self.__install_plan.items():
            section = section_data[0]
            data = section_data[1]
            for build_filepath, info in data.items():
                installpath = Path(self.__installed[build_filepath])
                destination = Path(info['destination'])
                if section == "python":
                    if destination.parts[0] == '{py_platlib}':
                        self.is_pure = False
                    self.distribution_files.append(str(installpath))
                elif destination.parts[0] == '{libdir_shared}':
                    self.platlibs += self.__targets[build_filepath]
                elif destination.parts[0] == '{module_shared}':
                    self.is_pure = False
                    self.distribution_files.append(str(installpath))
                elif installpath.suffix in data_infos:
                    data_infos[installpath.suffix].append(str(installpath))

    def __iter__(self):
        for p in self.__installed.values():
            yield p

    def __legacy_inspect(self):
        variables = sysconfig.get_config_vars()
        platlib_suffix = variables.get('EXT_SUFFIX') or variables.get(
            'SO') or variables.get('.so')
        # msys2's python3 has "-cpython-36m.dll", we have to be clever
        split = platlib_suffix.rsplit('.', 1)

        platlib_suffix = f".{split.pop(-1)}"
        data_infos = {
            ".typelib": self.typelibs,
        }

        install_paths = self.__installed.values()
        for installpath in install_paths:
            installpath = Path(installpath)
            if installpath.suffix == platlib_suffix:
                self.is_pure = False

            if 'site-packages' in str(installpath):
                self.distribution_files.append(str(installpath))
            elif platlib_suffix in installpath.suffixes:
                self.platlibs.append(str(installpath))
            elif installpath.suffix in data_infos:
                data_infos[installpath.suffix].append(str(installpath))


    def get_wheel_path(self, file):
        installpath = Path(file)
        if str(installpath) in self.distribution_files:
            installpath = Path(file)
            path = Path()
            while installpath.name != 'site-packages':
                path = installpath.name / path
                installpath = installpath.parent

            return path

        elif file in self.platlibs:
            return f"{self.__config['module']}.libs" / Path(installpath.name)
        elif file in self.typelibs:
            return Path(f"{self.__config['module']}.data") / 'platlib' / 'girepository-1.0' / Path(installpath.name)

        self.debug(f"{file} won't be packed")
        return None


class Config(Logger):
    def __init__(self, config_settings: T.Dict[str, str], builddir=None):
        super().__init__(config_settings)
        config = self.__get_config()
        self.__set_metadata_backward_compat(config)
        self.__entry_points = config.get('tool', {}).get('mesonpep517', {}).get('entry-points', [])
        self.__install_plan = None
        self.options = []
        self.builddir = None
        if builddir:
            self.set_builddir(builddir)

    @property
    def install_plan(self):
        if self.__install_plan:
            return self.__install_plan

        self.__install_plan = InstallPlan(self, self.config_settings)

        return self.__install_plan

    def _warn_deprecated_field(self, field, replacement):
        log.warning(
            f"Field `tool.mesonpep517.metadata.{field}` is deprecated since version 0.3."
            f" Use {replacement} instead."
            " Note that its support will be removed in a future version"
        )

    def __set_metadata_backward_compat(self, config):
        self.__metadata = config.get('tool', {}).get('mesonpep517', {}).get('metadata', {})
        self.__config = self.__metadata.copy()
        self.__config.update(config.get('project', {}))

        projects_urls = config.get('project', {}).get('urls')
        if projects_urls:
            urls = []
            for label, url in projects_urls.items():
                urls.append(f'{label.capitalize()}, {url}')
            self.__config['project-urls'] = urls

        entry_points = {}
        entry_point_types = ['scripts', 'gui-scripts'] + list(config.get('project', {}).get('entry-points', {}).keys())
        for entry_point_type in entry_point_types:
            entry_point = config.get('project', {}).get(entry_point_type)
            if not entry_point:
                continue
            if not isinstance(entry_point, dict):
                raise RuntimeError(f"`project.{entry_point_type}` should be a dictionary")

            epoints = []
            for k, v in entry_point:
                epoints = f'{k} = {v}'
            entry_points[entry_point_type] = epoints

        if entry_points:
            self.__entry_points = entry_points

        for old_name, new_name in {
                'description-file': 'readme',
                'description': 'summary',
                'requires': 'dependencies'}.items():
            old_value = self.__config.pop(old_name, None)
            if old_value and not self.get(new_name):
                self._warn_deprecated_field(old_name, new_name)
                self[new_name] = old_value

        if 'license' in self and isinstance(self['license'], str):
            log.warning('Setting project.license to a string is deprecated.'
                        ' Use a table instead:\n'
                        '   [project]\n'
                        '   license = {text =  """License text here"""}\n')
            self['license'] = {'text': self['license']}

    def validate_options(self):
        options = VALID_OPTIONS.copy()
        options['version'] = {}
        options['module'] = {}
        for field, value in self.__config.items():
            if field not in options:
                raise RuntimeError("%s is not a valid option in the `[project]` section, "
                    "got value: %s" % (field, value))

            replacement = options[field].get('deprecated-by')
            if field in self.__metadata and replacement:
                self._warn_deprecated_field(field, replacement)
            del options[field]

        for field, desc in options.items():
            if desc.get('required'):
                raise RuntimeError("%s is mandatory in the `[tool.mesonpep517.metadata] section but was not found" % field)

    def introspect(self, introspect_type):
        with open(os.path.join(self.builddir, 'meson-info', 'intro-' + introspect_type + '.json')) as f:
            return json.load(f)

    def set_builddir(self, builddir: os.PathLike):
        self.builddir = builddir
        project = self.introspect('projectinfo')

        self['version'] = project['version']
        if 'module' not in self:
            self['module'] = project['descriptive_name']

        if "name" in self:
            self['module'] = self['name']

        self.options = self.introspect('buildoptions')
        self.validate_options()

    def __getitem__(self, key):
        return self.__config[key]

    def __setitem__(self, key, value):
        self.__config[key] = value

    def __contains__(self, key):
        return key in self.__config

    @staticmethod
    def __get_config():
        with open('pyproject.toml') as f:
            config = toml.load(f)
            try:
                config['tool']['mesonpep517']['metadata']
                try:
                    config['project']
                except KeyError:
                    raise RuntimeError("`[project]` section is mandatory "
                        "for the meson backend")
            except:
                pass

            return config

    def get(self, key, default=None):
        return self.__config.get(key, default)

    def get_metadata(self):
        meta = {
            'name': self['module'],
            'version': self['version'],
        }

        if 'pkg-info-file' in self:
            res = '\n'.join(PKG_INFO.split('\n')[:3]).format(**meta) + '\n'
            with open(self['pkg-info-file'], 'r') as f:
                orig_lines = f.readlines()
                for l in orig_lines:
                    if l.startswith('Metadata-Version:') or \
                            l.startswith('Version:'):
                        continue
                    res += l

            return  res

        res = PKG_INFO.format(**meta)

        for key, metadata in [
                ('description', 'Summary'),
                ('home-page', None),
                ('homepage', None),
                ('author', None),
                ('author-email', None),
                ('maintainer', None),
                ('maintainer-email', None)]:
            if key in self:
                metadata = metadata or key.capitalize()
                res += '{}: {}\n'.format(metadata, self[key])

        for key in ['authors', 'maintainers']:
            authors = self.get(key, [])
            for author in authors:
                if 'name' in author:
                    res += f"{key[:-1].capitalize()}: {author['name']}\n"
                if 'email' in author:
                    res += f"{key[:-1].capitalize()}-email: {author['email']}\n"

        if key == 'requires-python' and key in self:
            res += '{}: {}\n'.format(key.title(), self[key])

        for key, mdata_key in [
                ('dependencies', 'Requires-Dist'),
                ('classifiers', 'Classifier'),
                ('project-urls', 'Project-URL')]:

            vals = self.get(key, [])
            for val in vals:
                res += '{}: {}\n'.format(mdata_key, val)

        license = None
        if 'license' in self:
            license = self['license'].get('text')
            if not license:
                license_file = self['license'].get('file')
                if license_file:
                    with open(license_file, 'r') as f:
                        license = f.read()
            elif self['license'].get('file'):
                raise RuntimeError('license field can only have one of text or file.')

        if license:
            res += 'License:\n'
            for line in license.split('\n'):
                res += ' ' * 7 + '|{}\n'.format(line)

        readme = ''
        description_content_type = 'text/plain'
        if 'readme' in self:
            description_file = Path(self['readme'])
            with open(description_file, 'r') as f:
                readme = f.read()

            description_content_type = readme_ext_to_content_type.get(
                description_file.suffix.lower(), description_content_type)
        elif 'description' in self:
            readme = self['description']

        if readme:
            res += 'Description-Content-Type: {}\n'.format(description_content_type)
            res += 'Description:\n\n' + readme

        return res

    def get_entry_points(self):
        res = ''
        for group_name in sorted(self.__entry_points):
            res += '[{}]\n'.format(group_name)
            group = self.__entry_points[group_name]
            for entrypoint in sorted(group):
                res += '{}\n'.format(entrypoint)
            res += '\n'

        return res


@contextlib.contextmanager
def cd(path):
    CWD = os.getcwd()

    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(CWD)


def get_requires_for_build_wheel(config_settings: T.Dict[str, str]):
    """Returns a list of requirements for building, as strings"""
    return Config(config_settings).get('dependencies', [])


# For now, we require all dependencies to build either a wheel or an sdist.
get_requires_for_build_sdist = get_requires_for_build_wheel


wheel_file_template = """\
Wheel-Version: 1.0
Generator: mesonpep517
Root-Is-Purelib: {is_pure}
Tag: {tag}
"""


def _write_wheel_file(f, is_pure, wheel_tag):
    f.write(wheel_file_template.format(is_pure=str(is_pure).lower(),
                                       tag=wheel_tag))

class NoPythonVersion(Exception):
    """
    Raised when a package specifies requires-python versions which cannot
    match any versions.
    """
    pass


def _py3_only(supports_py2, supports_py3):
    if supports_py3 is False:
        raise NoPythonVersion('No versions of python have been allowed')

    supports_py3 = True
    supports_py2 = False

    return (supports_py2, supports_py3)


def _py2_only(supports_py2, supports_py3):
    if supports_py2 is False:
        raise NoPythonVersion('No versions of python have been allowed')

    supports_py3 = False
    supports_py2 = True

    return (supports_py2, supports_py3)


def _py2_or_py3(supports_py2, supports_py3):
    if supports_py2 is None:
        supports_py2 = True
    if supports_py3 is None:
        supports_py3 = True

    return (supports_py2, supports_py3)


def python_major_support(python_requirements):
    """
    Process version specifiers tell whether python2 or python3 are supported.

    :arg python_requirements: A string containing version specifiers.  These
        should correspond to the versions of python that are supported. If no
        vesions are specified, both python2 and 3 are assumed to be supported.
    :returns: A tuple of booleans.  The first value is whether python2 is
        supported.  The second is whether python3 is supported.
    :raises NoPythonVersion: When the requirements would exclude both python2
        and python3.
    """
    # Backwards compat: mesonpep517 older than 0.2 allowed py2 and py3 in
    # its requires-python field.  The old format also allowed things like py35
    # but we're not going to handle those as their meaning would have been
    # very bad for packagers anyway.
    compat_from_old_format = None
    old_format_python_versions = python_requirements.split('.')
    if 'py2' in old_format_python_versions:
        if 'py3' in old_format_python_versions:
            compat_from_old_format = (True, True)
        compat_from_old_format = (True, False)
    if 'py3' in old_format_python_versions:
        compat_from_old_format = (False, True)

    if compat_from_old_format:
        log.warning('Specifying `requires-python:` as `py2` or `py3` is'
                    ' deprecated since version 0.3. Use version specifiers'
                    ' (ex: `requires-python: ~=3`) instead.  Support for'
                    ' `py2` and `py3` will be removed in a future version')
        return compat_from_old_format

    python_specifiers = SpecifierSet(python_requirements)

    # The user has not specified what versions of python we run on
    if not python_specifiers:
        # Note: the other reasonable default would be to only list True for the
        # python major which corresponds to the interpreter returned by
        # _which_python().
        return (True, True)

    # packaging will parse specifiers but it doesn't have a way to say:
    # "Does this specification allow any $MAJOR version X?" so we need to
    # examine the specifiers ourselves.

    supports_py2 = supports_py3 = None
    for spec in python_specifiers:
        version = Version(spec.version)

        if spec.operator in ('==', '~='):
            if version.major == 3:
                supports_py2, supports_py3 = _py3_only(supports_py2, supports_py3)
            elif version.major == 2:
                supports_py2, supports_py3 = _py2_only(supports_py2, supports_py3)
            else:  # version.major is neither 2 nor 3
                raise NoPythonVersion('Packages must support either Python2 or'
                                      f' Python3 but `{spec}` precludes that.')

        if spec.operator == '>=':
            if version.major == '3':
                supports_py2, supports_py3 = _py3_only(supports_py2, supports_py3)
            elif version.major <= '2':
                supports_py2, supports_py3 = _py2_or_py3(supports_py2, supports_py3)
            else:  # version.major is greater than 3
                raise NoPythonVersion('Packages must support either Python2 or'
                                      f' Python3 but `{spec}` precludes that.')

        if spec.operator in ('<='):
            if version.major >= 3:
                supports_py2, supports_py3 = _py2_or_py3(supports_py2, supports_py3)
            if version.major == 2:
                supports_py2, supports_py3 = _py2_only(supports_py2, supports_py3)
            else:  # version.major is less than 2
                raise NoPythonVersion('Packages must support either Python2 or'
                                      f' Python3 but `{spec}` precludes that.')

        if spec.operator == '>':
            if version.major == 3:
                supports_py2, supports_py3 = _py3_only(supports_py2, supports_py3)
            if version.major <= 2:
                supports_py2, supports_py3 = _py2_or_py3(supports_py2, supports_py3)
            else:  # version.major is greater than 3
                raise NoPythonVersion('Packages must support either Python2 or'
                                      f' Python3 but `{spec}` precludes that.')

        if spec.operator == '<':
            if version.major >= 3:
                supports_py2, supports_py3 = _py2_only(supports_py2, supports_py3)
            if version.major == 2:
                if version == Version('2.0.0'):
                    # version.major is less than 2.0
                    raise NoPythonVersion('Packages must support either'
                                          f' Python2 or Python3 but `{spec}`'
                                          ' precludes that.')
                # Specifier is something like "<2.3" so python2 is supported
                supports_py2, supports_py3 = _py2_only(supports_py2, supports_py3)
            else:  # version.major is less than 2
                raise NoPythonVersion('Packages must support either Python2 or'
                                      f' Python3 but `{spec}` precludes that.')

    # Note: unlike ealier checks, this one processes None as False-y.
    # That way, the logic is:
    # * If the user specified requires-python in pyproject.toml
    # AND
    #   * There were no python2 or python3 versions specified,
    #   OR
    #   * The user specified versions eliminate both python2 and python3
    # THEN
    #   Raise an Exception
    if not supports_py2 and not supports_py3:
        raise NoPythonVersion('requires-python does not allow any versions'
                              ' of python')

    return (supports_py2, supports_py3)


GET_CHECK = """
from mesonpep517 import pep425tags
print("{0}{1}-{2}".format(pep425tags.get_abbr_impl(),
                          pep425tags.get_impl_ver(),
                          pep425tags.get_abi_tag())
)
"""


def get_impl_abi(python):
    return subprocess.check_output([python, '-c', GET_CHECK]).decode('utf-8').strip()


def _which_python(config):
    python = 'python3'
    option_build = config.get('meson-python-option-name')
    if not option_build:
        python = 'python3'
        log.info("meson-python-option-name not specified in the"
                 " [tool.mesonpep517.metadata] section, assuming `python3`")
    else:
        for opt in config.options:
            if opt['name'] == 'python_version':
                python = opt['value']
                break
    return python


def get_wheel_tag(config, is_pure):
    # Please see https://gitlab.com/thiblahute/mesonpep517/-/issues/12 for
    # the future of the platforms config option
    platform_tag = config.get(
        'platforms',
        'any' if is_pure else get_platform_tag()
    )

    if is_pure:
        supports_py2, supports_py3 = python_major_support(
            config.get('requires-python', ''))
        if supports_py2 and supports_py3:
            impl_tag = 'py2.py3'
        elif supports_py2:
            impl_tag = 'py2'
        else:
            impl_tag = 'py3'
        return '{}-none-{}'.format(impl_tag, platform_tag)

    # Contains compiled extensions
    python = _which_python(config)
    impl_abi = get_impl_abi(python)

    # Note that this doesn't handle manylinux yet.
    return '{0}-{1}'.format(
        impl_abi,
        platform_tag
    )


def prepare_metadata_for_build_wheel(metadata_directory,
                                     config_settings: T.Dict[str, str],
                                     builddir=None,
                                     config=None):
    """Creates {metadata_directory}/foo-1.2.dist-info"""
    had_config = config is not None
    if not config:
        config = Config(config_settings)

    if not builddir:
        builddir = tempfile.TemporaryDirectory().name

        MesonSetupCommand(config, builddir=builddir, config_settings=config_settings).execute()

    if not had_config:
        config.set_builddir(builddir)

    dist_info = Path(metadata_directory, '{}-{}.dist-info'.format(
                     config['module'], config['version']))
    dist_info.mkdir(exist_ok=True)

    is_pure = config.install_plan.is_pure
    wheel_tag = get_wheel_tag(config, is_pure)
    with (dist_info / 'WHEEL').open('w') as f:
        _write_wheel_file(f, is_pure, wheel_tag)

    with (dist_info / 'METADATA').open('w') as f:
        f.write(config.get_metadata())

    entrypoints = config.get_entry_points()
    if entrypoints:
        with (dist_info / 'entry_points.txt').open('w') as f:
            f.write(entrypoints)

    return dist_info.name


class WheelBuilder(Logger):
    def __init__(self, config_settings: T.Dict[str, str]):
        super().__init__(config_settings)
        self.wheel_zip = None
        self.builddir = tempfile.TemporaryDirectory()
        self.installdir = tempfile.TemporaryDirectory()

    def build(self, wheel_directory: str, metadata_dir: str):
        config = Config(self.config_settings)

        MesonSetupCommand(config, self.installdir.name, self.builddir.name, config_settings=self.config_settings).execute()
        config.set_builddir(self.builddir.name)

        metadata_dir = prepare_metadata_for_build_wheel(
            wheel_directory, builddir=self.builddir.name,
            config_settings=self.config_settings, config=config)

        wheel_tag = get_wheel_tag(config, config.install_plan.is_pure)

        target_fp = wheel_directory / '{}-{}-{}.whl'.format(
            config['module'], config['version'], wheel_tag)

        self.wheel_zip = WheelFile(str(target_fp), 'w')
        for f in os.listdir(str(wheel_directory / metadata_dir)):
            self.wheel_zip.write(str(wheel_directory / metadata_dir / f),
                arcname=str(Path(metadata_dir) / f))

        # Make sure everything is built
        MesonInstallCommand('-C', self.builddir.name, config_settings=self.config_settings).execute()
        self.pack_files(config)
        self.wheel_zip.close()
        return str(target_fp)


    def pack_files(self, config):
        install_plan = config.install_plan
        for installpath in install_plan:
            wheel_path = install_plan.get_wheel_path(installpath)
            if wheel_path:
                self.debug(f"{installpath}-----> {wheel_path}")
                self.wheel_zip.write(installpath, arcname=str(wheel_path))


def build_wheel(wheel_directory,
                config_settings: T.Dict[str, str],
                metadata_directory=None):
    """Builds a wheel, places it in wheel_directory"""
    return WheelBuilder(config_settings).build(Path(
        wheel_directory), metadata_directory)


def build_sdist(sdist_directory, config_settings: T.Dict[str, str]):
    """Builds an sdist, places it in sdist_directory"""
    distdir = Path(sdist_directory)
    with tempfile.TemporaryDirectory() as builddir:
        with tempfile.TemporaryDirectory() as installdir:
            config = Config(config_settings)

            MesonSetupCommand(config, installdir, builddir,
                config_settings=config_settings).execute()

            config.set_builddir(builddir)
            mesondistcmd = MesonDistCommand('-C', builddir, config_settings=config_settings)
            mesondistcmd.execute()

            formats = mesondistcmd.formats()
            # assert here, because this can't be None if the subprocess exited with a 0 return code
            assert formats
            tf_dir = '{}-{}'.format(config['module'], config['version'])
            mesondistfilename = f'{tf_dir}{mesondistcmd.file_extenstion(formats[0])}'
            if formats[0] == 'gztar' or formats[0] == 'xztar':
                mesondistarch = tarfile.open(
                    Path(builddir) / 'meson-dist' / mesondistfilename)
            else:
                mesondistarch = zipfile.ZipFile(Path(builddir) / 'meson-dist' / mesondistfilename)
            mesondistarch.extractall(installdir)

            pkg_info = config.get_metadata()
            distfilename = '%s.tar.gz' % tf_dir
            target = distdir / distfilename
            source_date_epoch = os.environ.get('SOURCE_DATE_EPOCH', '')
            mtime = int(source_date_epoch) if source_date_epoch else None
            with GzipFile(str(target), mode='wb', mtime=mtime) as gz:
                with cd(installdir):
                    with tarfile.TarFile(str(target), mode='w',
                                         fileobj=gz,
                                         format=tarfile.PAX_FORMAT) as tf:
                        tf.add(tf_dir, recursive=True)
                        pkginfo_path = Path(installdir) / tf_dir / 'PKG-INFO'
                        with open(pkginfo_path, mode='w') as fpkginfo:
                            fpkginfo.write(pkg_info)
                            fpkginfo.flush()
                            tf.add(Path(tf_dir) / 'PKG-INFO')
    return target.name
