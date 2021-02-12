#
# The pep425tag modules includes (slightly altered) code from the
# 'wheel.pep452tags' module of the 'wheel' project
# <https://pypi.org/project/wheel>, released under the MIT license.
#
# The original license text from the wheel project is reproduced below:
#
# "wheel" copyright (c) 2012-2014 Daniel Holth <dholth@fastmail.fm> and
# contributors.
#
# The MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
"""Generate PEP 425 compatibility tags."""

import distutils.util
import platform
import sys
import sysconfig
import warnings


def get_abbr_impl():
    """Return abbreviated implementation name."""
    impl = platform.python_implementation()
    if impl == "PyPy":
        return "pp"
    elif impl == "Jython":
        return "jy"
    elif impl == "IronPython":
        return "ip"
    elif impl == "CPython":
        return "cp"

    raise LookupError("Unknown Python implementation: " + impl)


def get_abi_tag():
    """Return the ABI tag based on SOABI (if available) or emulate SOABI
    (CPython 2, PyPy)."""
    soabi = get_config_var("SOABI")
    impl = get_abbr_impl()
    if not soabi and impl in ("cp", "pp") and hasattr(sys, "maxunicode"):
        d = ""
        m = ""
        u = ""

        precond = impl == "cp"
        if get_flag("Py_DEBUG", hasattr(sys, "gettotalrefcount"), warn=precond):
            d = "d"

        precond = impl == "cp" and sys.version_info < (3, 3)
        if sys.version_info < (3, 8) and get_flag(
            "WITH_PYMALLOC", (impl == "cp"), warn=precond
        ):
            m = "m"

        precond = impl == "cp" and sys.version_info < (3, 8)
        if sys.version_info < (3, 3) and get_flag(
            "Py_UNICODE_SIZE",
            (sys.maxunicode == 0x10FFFF),
            expected=4,
            warn=precond,
        ):
            u = "u"

        abi = "%s%s%s%s%s" % (impl, get_impl_ver(), d, m, u)
    elif soabi and soabi.startswith("cpython-"):
        abi = "cp" + soabi.split("-")[1]
    elif soabi:
        abi = soabi.replace(".", "_").replace("-", "_")
    else:
        abi = None
    return abi


def get_config_var(var, default=None):
    """Return value of given sysconfig variable or given default value, if it
    is not set."""
    try:
        return sysconfig.get_config_var(var)
    except IOError as e:  # pip Issue #1074
        warnings.warn("{0}".format(e), RuntimeWarning)
        return default


def get_flag(var, fallback, expected=True, warn=True):
    """Use a fallback method for determining SOABI flags if the needed config
    var is unset or unavailable."""
    val = get_config_var(var)
    if val is None:
        if warn:
            warnings.warn(
                "Config variable '{0}' is unset, Python ABI tag may "
                "be incorrect".format(var),
                RuntimeWarning,
                2,
            )
        return fallback
    return val == expected


def get_impl_ver():
    """Return implementation version."""
    impl_ver = get_config_var("py_version_nodot")
    if not impl_ver:
        impl_ver = "{}{}".format(*sys.version_info[:2])
    return impl_ver


def get_platform_tag():
    """Return the PEP-425 compatible platform tag."""
    return distutils.util.get_platform().replace("-", "_").replace(".", "_")
