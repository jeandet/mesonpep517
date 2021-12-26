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
from wheel.bdist_wheel import get_platform

from .schema import VALID_OPTIONS

log = logging.getLogger(__name__)


class MesonCommand(abc.ABC):
    __exe = 'meson'

    def __init__(self, subcommand: str, *args: str, builddir: str, config_settings: T.Dict[str, str]={}) -> None:
        if config_settings:
            extra_args = config_settings.get(f'--{subcommand}-args')
        else:
            extra_args = None
        if extra_args:
            self.args = tuple([subcommand, *shlex.split(shlex.quote(extra_args), posix=True), *args])
        else:
            self.args = tuple([subcommand, *args])

        self.builddir = builddir

    def execute(self) -> bytes:
        try:
            return subprocess.check_output([self.__exe, *self.args])
        except subprocess.CalledProcessError as e:
            stdout = ''
            stderr = ''
            if e.stdout:
                stdout = e.stdout.decode()
            if e.stderr:
                stderr = e.stderr.decode()
            print("Could not run meson: %s\n%s" % (stdout, stderr), file=sys.stderr)
            fulllog = os.path.join(self.builddir, 'meson-logs', 'meson-log.txt')
            try:
                with open(fulllog) as f:
                    print("Full log: %s" % f.read())
            except:
                print("Could not open %s" % fulllog)
                pass
            raise e


class MesonSetupCommand(MesonCommand):
    """First arg must be the builddir"""
    def __init__(self, *args: str, config_settings: T.Dict[str, str]={}) -> None:
        # Protect against user overriding prefix
        if config_settings:
            extra_args = config_settings.get("--setup-args", "")
            for arg in shlex.split(shlex.quote(extra_args), posix=True):
                if arg.startswith(("-Dprefix=", "--prefix")):
                    print("mesonpep517 does not support overriding the prefix")
                    sys.exit(1)
        MesonCommand.__init__(self, 'setup', *args, builddir=args[0], config_settings=config_settings)


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
                print('Invalid "--formats" option. Please read Meson documentation for help.', file=sys.stderr)
                return None
            group = match.groups()[0]
            if not group:
                print('Invalid "--formats" option. Please read Meson documentation for help.', file=sys.stderr)
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


class Config:
    def __init__(self, builddir=None):
        config = self.__get_config()
        self.__set_metadata_backward_compat(config)
        self.__entry_points = config.get('tool', {}).get('mesonpep517', {}).get('entry-points', [])
        self.installed = []
        self.options = []
        self.builddir = None
        if builddir:
            self.set_builddir(builddir)

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

    def __introspect(self, introspect_type):
        with open(os.path.join(self.__builddir, 'meson-info', 'intro-' + introspect_type + '.json')) as f:
            return json.load(f)

    def set_builddir(self, builddir):
        self.__builddir = builddir
        project = self.__introspect('projectinfo')

        self['version'] = project['version']
        if 'module' not in self:
            self['module'] = project['descriptive_name']

        if "name" in self:
            self['module'] = self['name']

        self.installed = self.__introspect('installed')
        self.options = self.__introspect('buildoptions')
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
    return Config().get('dependencies', [])


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


def check_is_pure(installed):
    variables = sysconfig.get_config_vars()
    suffix = variables.get('EXT_SUFFIX') or variables.get(
        'SO') or variables.get('.so')
    # msys2's python3 has "-cpython-36m.dll", we have to be clever
    split = suffix.rsplit('.', 1)
    suffix = split.pop(-1)

    for installpath in installed.values():
        if "site-packages" in installpath:
            if installpath.split('.')[-1] == suffix:
                return False

    return True


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
from packaging import tags
from wheel import bdist_wheel
print("{0}{1}-{2}".format(tags.interpreter_name(),
                          tags.interpreter_version(),
                          bdist_wheel.get_abi_tag())
)
"""


def get_impl_abi(python):
    return subprocess.check_output([python, '-c', GET_CHECK]).decode('utf-8').strip()


def _which_python(config):
    log.info(f'config.options: {config.options}')
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
                log.info(f"using python: {python}")
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


def get_platform_tag():
    """Return the PEP-425 compatible platform tag."""
    return get_platform(None).replace("-", "_").replace(".", "_")


def prepare_metadata_for_build_wheel(metadata_directory,
                                     config_settings: T.Dict[str, str],
                                     builddir=None,
                                     config=None):
    """Creates {metadata_directory}/foo-1.2.dist-info"""
    if not builddir:
        builddir = tempfile.TemporaryDirectory().name
        MesonSetupCommand(builddir, config_settings=config_settings).execute()
    if not config:
        config = Config(builddir)

    dist_info = Path(metadata_directory, '{}-{}.dist-info'.format(
                     config['module'], config['version']))
    dist_info.mkdir(exist_ok=True)

    is_pure = check_is_pure(config.installed)
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


class WheelBuilder:
    def __init__(self):
        self.wheel_zip = None
        self.builddir = tempfile.TemporaryDirectory()
        self.installdir = tempfile.TemporaryDirectory()

    def build(self, wheel_directory, config_settings: T.Dict[str, str], metadata_dir):
        config = Config()

        args = [self.builddir.name, '--prefix', self.installdir.name] + config.get('meson-options', [])
        option_build = config.get('meson-python-option-name')
        if option_build:
            args.append(f"-D{option_build}={_which_python(config)}")

        MesonSetupCommand(*args, config_settings=config_settings).execute()
        config.set_builddir(self.builddir.name)

        metadata_dir = prepare_metadata_for_build_wheel(
            wheel_directory, builddir=self.builddir.name,
            config_settings=config_settings, config=config)

        is_pure = check_is_pure(config.installed)
        wheel_tag = get_wheel_tag(config, is_pure)

        target_fp = wheel_directory / '{}-{}-{}.whl'.format(
            config['module'], config['version'], wheel_tag)

        self.wheel_zip = WheelFile(str(target_fp), 'w')
        for f in os.listdir(str(wheel_directory / metadata_dir)):
            self.wheel_zip.write(str(wheel_directory / metadata_dir / f),
                arcname=str(Path(metadata_dir) / f))

        # Make sure everything is built
        MesonInstallCommand('-C', self.builddir.name, config_settings=config_settings).execute()
        self.pack_files(config)
        self.wheel_zip.close()
        return str(target_fp)

    def pack_files(self, config):
        for _, installpath in config.installed.items():
            if "site-packages" in installpath:
                while os.path.basename(installpath) != 'site-packages':
                    installpath = os.path.dirname(installpath)
                self.wheel_zip.write_files(installpath)
                break


def build_wheel(wheel_directory,
                config_settings: T.Dict[str, str],
                metadata_directory=None):
    """Builds a wheel, places it in wheel_directory"""
    return WheelBuilder().build(Path(
        wheel_directory), config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings: T.Dict[str, str]):
    """Builds an sdist, places it in sdist_directory"""
    distdir = Path(sdist_directory)
    with tempfile.TemporaryDirectory() as builddir:
        with tempfile.TemporaryDirectory() as installdir:
            config = Config()

            args = [builddir, '--prefix', installdir] + config.get('meson-options', [])
            option_build = config.get('meson-python-option-name')
            if option_build:
                args.append(f"-D{option_build}={_which_python(config)}")

            MesonSetupCommand(*args, config_settings=config_settings).execute()

            config = Config(builddir)
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
