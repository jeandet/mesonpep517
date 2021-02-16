"""PEP-517 compliant buildsystem API"""
import contextlib
import sysconfig
import logging
import sys
import tempfile
import tarfile
import os
import json
import subprocess
import toml

from gzip import GzipFile
from pathlib import Path
from wheel.wheelfile import WheelFile

from .pep425tags import get_abbr_impl, get_abi_tag, get_impl_ver, get_platform_tag
from .schema import VALID_OPTIONS

log = logging.getLogger(__name__)


def meson(*args, config_settings=None, builddir=''):
    try:
        return subprocess.check_output(['meson'] + list(args))
    except subprocess.CalledProcessError as e:
        stdout = ''
        stderr = ''
        if e.stdout:
            stdout = e.stdout.decode()
        if e.stderr:
            stderr = e.stderr.decode()
        print("Could not run meson: %s\n%s" % (stdout, stderr), file=sys.stderr)
        try:
            fulllog = os.path.join(builddir, 'meson-logs', 'meson-log.txt')
            with open(fulllog) as f:
                print("Full log: %s" % f.read())
        except:
            print("Could not open %s" % fulllog)
            pass
        raise e


def meson_configure(*args, config_settings=None):
    if 'MESON_ARGS' in os.environ:
       args = os.environ.get('MESON_ARGS').split(' ') + list(args)
       print("USING MESON_ARGS: %s" % args)
    args = list(args)
    args.append('-Dlibdir=lib')

    meson(*args, builddir=args[0], config_settings=config_settings)


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
        self.__metadata = config['tool']['mesonpep517']['metadata']
        self.__entry_points = config['tool']['mesonpep517'].get('entry-points', [])
        self.installed = []
        self.options = []
        self.builddir = None
        if builddir:
            self.set_builddir(builddir)

    def validate_options(self):
        options = VALID_OPTIONS.copy()
        options['version'] = {}
        options['module'] = {}
        for field, value in self.__metadata.items():
            if field not in options:
                raise RuntimeError("%s is not a valid option in the `[tool.mesonpep517.metadata]` section, "
                    "got value: %s" % (field, value))
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

        self.installed = self.__introspect('installed')
        self.options = self.__introspect('buildoptions')
        self.validate_options()

    def __getitem__(self, key):
        return self.__metadata[key]

    def __setitem__(self, key, value):
        self.__metadata[key] = value

    def __contains__(self, key):
        return key in self.__metadata

    @staticmethod
    def __get_config():
        with open('pyproject.toml') as f:
            config = toml.load(f)
            try:
                metadata = config['tool']['mesonpep517']['metadata']
            except KeyError:
                raise RuntimeError("`[tool.mesonpep517.metadata]` section is mandatory "
                    "for the meson backend")

            return config

    def get(self, key, default=None):
        return self.__metadata.get(key, default)

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

        for key in [
                'summary',
                'home-page',
                'author',
                'author-email',
                'maintainer',
                'maintainer-email',
                'license']:
            if key in self:
                res += '{}: {}\n'.format(key.capitalize(), self[key])

        for key, mdata_key in [
                ('requires', 'Requires-Dist'),
                ('classifiers', 'Classifier'),
                ('project-urls', 'Project-URL')]:

            vals = self.get(key, [])
            for val in vals:
                res += '{}: {}\n'.format(mdata_key, val)

        description = ''
        description_content_type = 'text/plain'
        if 'description-file' in self:
            description_file = Path(self['description-file'])
            with open(description_file, 'r') as f:
                description = f.read()

            description_content_type = readme_ext_to_content_type.get(
                description_file.suffix.lower(), description_content_type)
        elif 'description' in self:
            description = self['description']

        if description:
            res += 'Description-Content-Type: {}\n'.format(description_content_type)
            res += 'Description:\n\n' + description

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


def get_requires_for_build_wheel(config_settings=None):
    """Returns a list of requirements for building, as strings"""
    return Config().get('requires', [])


# For now, we require all dependencies to build either a wheel or an sdist.
get_requires_for_build_sdist = get_requires_for_build_wheel


wheel_file_template = """\
Wheel-Version: 1.0
Generator: mesonpep517
Root-Is-Purelib: {}
"""


def _write_wheel_file(f, supports_py2, is_pure):
    f.write(wheel_file_template.format(str(is_pure).lower()))
    if is_pure:
        if supports_py2:
            f.write("Tag: py2-none-any\n")
        f.write("Tag: py3-none-any\n")
    else:
        f.write("Tag: {0}{1}-{2}-{3}\n".format(
            get_abbr_impl(),
            get_impl_ver(),
            get_abi_tag(),
            get_platform_tag()
        ))


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


def prepare_metadata_for_build_wheel(metadata_directory,
                                     config_settings=None,
                                     builddir=None,
                                     config=None):
    """Creates {metadata_directory}/foo-1.2.dist-info"""
    if not builddir:
        builddir = tempfile.TemporaryDirectory().name
        meson_configure(builddir, config_settings=config_settings)
    if not config:
        config = Config(builddir)

    dist_info = Path(metadata_directory, '{}-{}.dist-info'.format(
                     config['module'], config['version']))
    dist_info.mkdir(exist_ok=True)

    is_pure = check_is_pure(config.installed)
    with (dist_info / 'WHEEL').open('w') as f:
        _write_wheel_file(f, False, is_pure)

    with (dist_info / 'METADATA').open('w') as f:
        f.write(config.get_metadata())

    entrypoints = config.get_entry_points()
    if entrypoints:
        with (dist_info / 'entry_points.txt').open('w') as f:
            f.write(entrypoints)

    return dist_info.name


GET_CHECK = """
from mesonpep517 import pep425tags
print("{0}{1}-{2}".format(pep425tags.get_abbr_impl(),
                          pep425tags.get_impl_ver(),
                          pep425tags.get_abi_tag())
)
"""


def get_abi(python):
    return subprocess.check_output([python, '-c', GET_CHECK]).decode('utf-8').strip('\n')


class WheelBuilder:
    def __init__(self):
        self.wheel_zip = None
        self.builddir = tempfile.TemporaryDirectory()
        self.installdir = tempfile.TemporaryDirectory()

    def build(self, wheel_directory, config_settings, metadata_dir):
        config = Config()

        args = [self.builddir.name, '--prefix', self.installdir.name] + config.get('meson-options', [])
        meson_configure(*args, config_settings=config_settings)
        config.set_builddir(self.builddir.name)

        metadata_dir = prepare_metadata_for_build_wheel(
            wheel_directory, builddir=self.builddir.name,
            config=config)

        is_pure = check_is_pure(config.installed)
        platform_tag = config.get(
            'platforms',
            'any' if is_pure else get_platform_tag()
        )

        if not is_pure:
            python = 'python3'
            option_build = config.get('meson-python-option-name')
            if not option_build:
                python = 'python3'
                log.warning("meson-python-option-name not specified in the " +
                    "[tool.mesonpep517.metadata] section, assuming `python3`")
            else:
                for opt in config.options:
                    if opt['name'] == 'python_version':
                        python = opt['value']
                        break
            abi = get_abi(python)
        else:
            abi = '{}-none'.format(config.get('requires-python', 'py3'))

        target_fp = wheel_directory / '{}-{}-{}-{}.whl'.format(
            config['module'], config['version'], abi, platform_tag,)

        self.wheel_zip = WheelFile(str(target_fp), 'w')
        for f in os.listdir(str(wheel_directory / metadata_dir)):
            self.wheel_zip.write(str(wheel_directory / metadata_dir / f),
                arcname=str(Path(metadata_dir) / f))

        # Make sure everything is built
        meson('install', '-C', self.builddir.name)
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
                config_settings=None,
                metadata_directory=None):
    """Builds a wheel, places it in wheel_directory"""
    return WheelBuilder().build(Path(
        wheel_directory), config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    """Builds an sdist, places it in sdist_directory"""
    distdir = Path(sdist_directory)
    with tempfile.TemporaryDirectory() as builddir:
        with tempfile.TemporaryDirectory() as installdir:
            meson(builddir, '--prefix', installdir,
                  config_settings=config_settings,
                  builddir=builddir)

            config = Config(builddir)
            meson('dist', '-C', builddir)

            tf_dir = '{}-{}'.format(config['module'], config['version'])
            mesondistfilename = '%s.tar.xz' % tf_dir
            mesondisttar = tarfile.open(
                Path(builddir) / 'meson-dist' / mesondistfilename)
            mesondisttar.extractall(installdir)

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
