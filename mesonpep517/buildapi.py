"""PEP-517 compliant buildsystem API"""
import contextlib
import sysconfig
import logging
import tempfile
import tarfile
import os
import json
import subprocess
import pytoml

from distutils import util
from gzip import GzipFile
from pathlib import Path
from wheel.wheelfile import WheelFile


log = logging.getLogger(__name__)


def meson(*args, config_settings=None):
    return subprocess.check_output(['meson'] + list(args))


def meson_introspect(_dir, introspect_type):
    with open(os.path.join(_dir, 'meson-info', 'intro-' + introspect_type + '.json')) as f:
        return json.load(f)


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
    return ['setuptools']


# For now, we require all dependencies to build either a wheel or an sdist.
get_requires_for_build_sdist = get_requires_for_build_wheel


wheel_file_template = """\
Wheel-Version: 1.0
Generator: mesonpep517
Root-Is-Purelib: {}
"""


def _write_wheel_file(f, supports_py2, is_pure):
    f.write(wheel_file_template.format(str(is_pure).lower()))
    if supports_py2:
        f.write("Tag: py2-none-any\n")
    f.write("Tag: py3-none-any\n")


PKG_INFO = """\
Metadata-Version: 2.1
Name: {name}
Version: {version}
Summary: {summary}
Home-page: {home_page}
Author: {author}
Author-email: {author_email}
"""


readme_ext_to_content_type = {
    '.rst': 'text/x-rst',
    '.md': 'text/markdown',
    '.txt': 'text/plain',
}

def get_metadata(project, config):
    meta = {
        'name': project['descriptive_name'],
        'version': project['version'],
    }

    configmeta = config['tool']['mesonpep517']['metadata']
    for key in ['summary', 'home_page', 'author', 'author_email']:
        meta[key] = configmeta[key.replace('_', '-')]

    description = ''
    description_content_type = 'text/plain'
    if 'description-file' in configmeta:
        description_file = Path(configmeta['description-file'])
        with open(description_file, 'r') as f:
            description = f.read()

        description_content_type = readme_ext_to_content_type.get(
            description_file.suffix, description_content_type)
    elif 'description' in configmeta:
        description = configmeta['description']
    meta['description_content_type'] = description_content_type
    res = PKG_INFO.format(**meta)

    for key, mdata_key in [
            ('requires_dist', 'Requires-Dist'),
            ('classifiers', 'Classifier'),
            ('project_urls', 'Project-URL')]:

        vals = configmeta.get(key, [])
        for val in vals:
            res += '{}: {}\n'.format(mdata_key, val)

    if description:
        res += 'Description-Content-Type: {description_content_type}\n'.format(
            **meta)
        res += 'Description:\n\n' + description

    return res


def get_entry_points(project, config):
    try:
        entrypoints = project['metadata']['python']['entry-points']
    except KeyError:
        try:
            entrypoints = config['tool']['mesonpep517']['entry-points']
        except KeyError:
            return None

    res = ''
    for group_name in sorted(entrypoints):
        res += '[{}]\n'.format(group_name)
        group = entrypoints[group_name]
        for entrypoint in sorted(group):
            res += '{}\n'.format(entrypoint)
        res += '\n'

    return res


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


def get_config():
    with open('pyproject.toml') as f:
        config = pytoml.load(f)
        try:
            configmeta = config['tool']['mesonpep517']['metadata']
        except KeyError:
            raise RuntimeError("`[tool.mesonpep517.metadata]` section is mandatory "
                "for the meson backend")

        
        return config


def prepare_metadata_for_build_wheel(metadata_directory,
                                     config_settings=None,
                                     builddir=None,
                                     config=None):
    """Creates {metadata_directory}/foo-1.2.dist-info"""
    if not builddir:
        builddir = tempfile.TemporaryDirectory().name
        meson(builddir, config_settings=config_settings)
    if not config:
        config = get_config()

    project = meson_introspect(builddir, 'projectinfo')

    dist_info = Path(metadata_directory, '{}-{}.dist-info'.format(
        project['descriptive_name'], project['version']))
    dist_info.mkdir(exist_ok=True)

    is_pure = check_is_pure(meson_introspect(builddir, 'installed'))
    with (dist_info / 'WHEEL').open('w') as f:
        _write_wheel_file(f, False, is_pure)

    with (dist_info / 'METADATA').open('w') as f:
        f.write(get_metadata(project, config))

    entrypoints = get_entry_points(project, config)
    if entrypoints:
        with (dist_info / 'entry_points.txt').open('w') as f:
            f.write(entrypoints)

    return dist_info.name


GET_CHECK = """
from wheel import pep425tags
print("{0}{1}-{2}".format(pep425tags.get_abbr_impl(),
      pep425tags.get_impl_ver(), pep425tags.get_abi_tag()))
"""


def get_abi(python):
    return subprocess.check_output([python, '-c', GET_CHECK]).decode('utf-8').strip('\n')


class WheelBuilder:
    def __init__(self):
        self.wheel_zip = None
        self.builddir = tempfile.TemporaryDirectory()
        self.installdir = tempfile.TemporaryDirectory()

    def introspect(self, introspect_type):
        return meson_introspect(self.builddir.name, introspect_type)

    def build(self, wheel_directory, config_settings, metadata_dir):
        args = [self.builddir.name, '--prefix', self.installdir.name]
        if 'MESON_ARGS' in os.environ:
            args += os.environ.get('MESON_ARGS').split(' ')
        meson(*args, config_settings=config_settings)

        config = get_config()
        metadata_dir = prepare_metadata_for_build_wheel(
            wheel_directory, builddir=self.builddir.name,
            config=config)
        project = self.introspect('projectinfo')
        installed_files = self.introspect('installed')

        is_pure = check_is_pure(installed_files)
        platform_tag = config.get(
            'platforms',
            'any' if is_pure else util.get_platform().replace('-', '_')
        )

        if not is_pure:
            python = 'python3'
            option_build = config['tool']['mesonpep517']['metadata'].get('meson-python-option-name')
            if not option_build:
                python = 'python3'
            else:
                log.warning("meson_python_option not specified in the " +
                    "[tool.mesonpep517.metadata] section, assuming `python3`")
                for opt in self.introspect('buildoptions'):
                    if opt['name'] == 'python_version':
                        python = opt['value']
                        break
            abi = get_abi(python)
        else:
            abi = '{}-none'.format(config.get('requires-python', 'py3'))

        target_fp = wheel_directory / '{}-{}-{}-{}.whl'.format(
            project['descriptive_name'],
            project['version'],
            abi,
            platform_tag,
        )
        self.wheel_zip = WheelFile(target_fp, 'w')
        for f in os.listdir(os.path.join(wheel_directory, metadata_dir)):
            self.wheel_zip.write(os.path.join(
                wheel_directory, metadata_dir, f),
                arcname=os.path.join(metadata_dir, f))

        # Make sure everything is built
        subprocess.check_call(['ninja', '-C', self.builddir.name, 'install'])
        for sfile, installpath in installed_files.items():
            if "site-packages" in installpath:
                while os.path.basename(installpath) != 'site-packages':
                    installpath = os.path.dirname(installpath)
                self.wheel_zip.write_files(installpath)
                break
        self.wheel_zip.close()
        return str(target_fp)


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
                  config_settings=config_settings)
            subprocess.check_call(['ninja', '-C', builddir, 'dist'])

            project = meson_introspect(builddir, 'projectinfo')

            tf_dir = '{}-{}'.format(project['descriptive_name'],
                                    project['version'])
            mesondistfilename = '%s.tar.xz' % tf_dir
            mesondisttar = tarfile.open(
                Path(builddir) / 'meson-dist' / mesondistfilename)
            mesondisttar.extractall(installdir)

            pkg_info = get_metadata(project, get_config())
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
