"""PEP-517 compliant buildsystem API"""
import contextlib
import sysconfig
import tempfile
import tarfile
import os
import sys
import json
import subprocess
import pytoml
import platform

from distutils import util
from gzip import GzipFile
from pathlib import Path
from wheel.wheelfile import WheelFile


def meson(*args, config_settings=None):
    return subprocess.check_output(['meson'] + list(args))


def meson_introspect(_dir, introspect_type):
    return json.loads(meson('introspect', _dir, '--' + introspect_type))


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
Description: {description}
Description-Content-Type: text/markdown
"""

def get_metadata(project):
    meta = {
        'name': project['descriptive_name'],
        'version': project['version'],
    }

    toml = pytoml.load(open('pyproject.toml'))
    try:
        pytomlmeta = toml['tool']['mesonpep517']['metadata']
    except KeyError:
        pytomlmeta = {}

    try:
        mesonmeta = project['metadata']['python']
    except KeyError:
        mesonmeta = {}

    for key in ['summary', 'home_page', 'author', 'author_email']:
        val = mesonmeta.get(key)
        if not val:
            val = pytomlmeta[key.replace('_', '-')]
        meta[key] = val

    description = ''
    if 'description' in pytomlmeta:
        description = pytomlmeta['description']
    elif 'description-file' in pytomlmeta:
        with open(pytomlmeta['description-file'], 'r') as f:
            description = '\n'
            for line in f.readlines():
                description += '    ' + line
    meta['description'] = description
    res = PKG_INFO.format(**meta)

    for key, mdata_key in [
            ('requires_dist', 'Requires-Dist'),
            ('classifiers', 'Classifier'),
            ('projects_urls', 'Project-URL')]:

        vals = mesonmeta.get(key)
        if not vals:
            vals = pytomlmeta.get(key, [])

        for val in vals:
            res += '{}: {}\n'.format(mdata_key, val)

    return res

def get_entry_points(project):
    try:
        entrypoints = project['metadata']['python']['entry-points']
    except KeyError:
        toml = pytoml.load(open('pyproject.toml'))
        try:
            entrypoints = toml['tool']['mesonpep517']['entry-points']
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

def get_python_install(installed):
    variables = sysconfig.get_config_vars()
    suffix = variables.get('EXT_SUFFIX') or variables.get('SO') or variables.get('.so')
    # msys2's python3 has "-cpython-36m.dll", we have to be clever
    split = suffix.rsplit('.', 1)
    suffix = split.pop(-1)

    pyvers = set()
    abi = 'none'
    is_pure = True
    for installpath in installed.values():
        if "site-packages" in installpath:
            dirname = os.path.dirname(installpath)
            while os.path.basename(dirname) != "site-packages":
                dirname = os.path.dirname(dirname)

            parent_dir = os.path.basename(os.path.dirname(dirname))
            if installpath.split('.')[-1] == suffix:
                is_pure = False
                filename = os.path.basename(installpath)
                fname_split = filename.split('.')[1].split('-')
                if fname_split[0] == 'cpython':
                    if abi == 'none':
                        abi = 'cp' + fname_split[1]
                    pyvers.add('cp' + fname_split[1][:-1])
                elif parent_dir == 'python2.7':
                    pyvers.add('cp27')
                    abi = 'cp27m'
                else:
                    raise RuntimeError('Python installation %s not handled' % parent_dir)
            else:
                if parent_dir.startswith('python'):
                    version = parent_dir[len("python"):]
                    if version[0].isdigit():
                        pyver = 'py' + version[0]
                        pyvers.add(pyver)

    if not is_pure:
        pyvers = [ver for ver in pyvers if 'cp' in ver]

    if not pyvers:
        pyvers = ['any']

    return is_pure, '.'.join(pyvers), abi

def prepare_metadata_for_build_wheel(metadata_directory,
                                     config_settings=None,
                                     builddir=None):

    """Creates {metadata_directory}/foo-1.2.dist-info"""
    if not builddir:
        builddir = tempfile.TemporaryDirectory().name
        meson(builddir, config_settings=config_settings)
    project = meson_introspect(builddir, 'projectinfo')

    dist_info = Path(metadata_directory, '{}-{}.dist-info'.format(
        project['descriptive_name'], project['version']))
    dist_info.mkdir(exist_ok=True)

    is_pure, _, _ = get_python_install(meson_introspect(builddir, 'installed'))
    with (dist_info / 'WHEEL').open('w') as f:
        _write_wheel_file(f, False, is_pure)

    with (dist_info / 'METADATA').open('w') as f:
        f.write(get_metadata(project))

    entrypoints = get_entry_points(project)
    if entrypoints:
        with (dist_info / 'entry_points.txt').open('w') as f:
            f.write(entrypoints)

    return dist_info.name


class WheelBuilder:
    def __init__(self):
        self.wheel_zip = None
        self.builddir = tempfile.TemporaryDirectory()
        self.installdir = tempfile.TemporaryDirectory()

    def build(self, wheel_directory, config_settings, metadata_dir):
        args = [self.builddir.name, '--prefix', self.installdir.name]
        if 'MESON_ARGS' in os.environ:
            args += os.environ.get('MESON_ARGS').split(' ')
        meson(*args, config_settings=config_settings)

        metadata_dir = prepare_metadata_for_build_wheel(
            wheel_directory, builddir=self.builddir.name)
        project = meson_introspect(self.builddir.name, 'projectinfo')
        installed_files = meson_introspect(self.builddir.name, 'installed')

        is_pure, pyver, abi = get_python_install(installed_files)
        platform_tag = 'any' if is_pure else util.get_platform().replace('-', '_')
        target_fp = wheel_directory / '{}-{}-{}-{}-{}.whl'.format(
            project['descriptive_name'],
            project['version'],
            pyver,
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

            pkg_info = get_metadata(project)
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
