#! /usr/bin/env python3
from typing import Union, Optional, Tuple, List, Dict, Sequence, Iterator, cast
import unittest
import subprocess
import logging
import inspect
import sys
import os
import collections
import shutil
import random
import re
import errno
from fnmatch import fnmatchcase as matches

try:
    from cStringIO import StringIO  # type: ignore[import, attr-defined]
except ImportError:
    from io import StringIO  # Python3

try:
    from urllib import quote_plus, urlretrieve  # type: ignore[import, attr-defined]
except ImportError:
    from urllib.parse import quote_plus  # Python3
    from urllib.request import urlretrieve  # Python3

if sys.version[0] == '3':
    basestring = str

logg = logging.getLogger("test")

topsrcdir = "../.."
testdatadir = "testdata.d"
readme = "README"
mkzip = "zip"
unzip = "unzip"
unzip_skip = False
exeext = ""
bindir = os.path.join("..", "bins")
downloaddir = "tmp.download"
downloadonly = False
nodownloads = False
KEEP = False

def yesno(text: str) -> bool:
    if not text: return False
    if text.lower() in ["y", "yes", "t", "true", "on", "ok"]:
        return True
    return False

def decodes(text: Union[str, bytes]) -> str:
    if text is None: return None
    if isinstance(text, bytes):
        encoded = sys.getdefaultencoding()
        if encoded in ["ascii"]:
            encoded = "utf-8"
        try:
            return text.decode(encoded)
        except:
            return text.decode("latin-1")
    return text

def shell_string(command: List[str]) -> str:
    return " ".join(["'%s'" % arg.replace("'", "\\'") for arg in command])

Shell = collections.namedtuple("Shell", ["returncode", "output", "errors", "shell"])
def shell(command: Union[str, List[str]], shell: bool = True,  # ..
          # ..
          calls: bool = False, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None, lang: Optional[str] = None,
          returncodes: Optional[Sequence[Optional[int]]] = None) -> Shell:
    returncodes = returncodes or [None, 0]
    if isinstance(command, basestring):
        sh_command = command
        command = [command]
    else:
        sh_command = shell_string(command)
    if not env:
        env = os.environ.copy()
    if lang:
        for name, value in env.items():
            if name.startswith("LC_"):
                env[name] = lang
        env["LANG"] = lang  # defines message format
        env["LC_ALL"] = lang  # other locale formats
    zzip_libs = "/zzip/.libs"
    zzip_cmds = command[0].split(" ")[0]
    build_lib1 = os.path.dirname(os.path.realpath(zzip_cmds))
    build_lib2 = os.path.dirname(build_lib1)
    build_lib3 = os.path.dirname(build_lib2)
    if os.path.isdir(build_lib1 + zzip_libs):
        env["LD_LIBRARY_PATH"] = build_lib1 + zzip_libs
    elif os.path.isdir(build_lib2 + zzip_libs):
        env["LD_LIBRARY_PATH"] = build_lib2 + zzip_libs
    elif os.path.isdir(build_lib3 + zzip_libs):
        env["LD_LIBRARY_PATH"] = build_lib3 + zzip_libs
    try:
        output, errors = "", ""
        if calls:
            logg.debug("result from %s: %s", cwd and cwd + "/" or "shell", sh_command)
            run = subprocess.Popen(command, shell=shell, cwd=cwd, env=env)
            if run.returncode:
                logg.warning("EXIT %s: %s", run.returncode, command)
            run.wait()
        else:
            logg.debug("output from %s: %s", cwd and cwd + "/" or "shell", sh_command)
            run = subprocess.Popen(command, shell=shell, cwd=cwd,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None, env=env)
            if run.returncode:
                logg.warning("EXIT %s: %s", run.returncode, command)
            out, err = run.communicate()
            output = decodes(out)
            errors = decodes(err)
    except:
        logg.error("*E*: %s", sh_command)
        for line in output.split("\n"):
            if line:
                logg.error("OUT: %s", line)
        for line in errors.split("\n"):
            if line:
                logg.error("ERR: %s", line)
        raise
    if run.returncode not in returncodes:
        logg.warning("*%02i: %s", run.returncode, sh_command)
        for line in output.split("\n"):
            if line:
                logg.warning("OUT: %s", line)
        for line in errors.split("\n"):
            if line:
                logg.warning("ERR: %s", line)
        raise subprocess.CalledProcessError(run.returncode, sh_command, output)
    else:
        for line in output.split("\n"):
            if line:
                logg.debug("OUT: %s", line)
        for line in errors.split("\n"):
            if line:
                logg.debug("ERR: %s", line)
    return Shell(run.returncode, output, errors, sh_command)

def get_caller_name() -> str:
    frame = inspect.currentframe().f_back.f_back  # type: ignore[union-attr]
    return frame.f_code.co_name  # type: ignore[union-attr]
def get_caller_caller_name() -> str:
    frame = inspect.currentframe().f_back.f_back.f_back  # type: ignore[union-attr]
    return frame.f_code.co_name  # type: ignore[union-attr]

def download_raw(base_url: str, filename: str, into: Optional[str], style: str = "?raw=true") -> Union[None, bool, str]:
    return download(base_url, filename, into, style)
def download(base_url: str, filename: str, into: Optional[str] = None, style: str = "") -> Union[None, bool, str]:
    if nodownloads:
        return False
    data = downloaddir
    if not os.path.isdir(data):
        os.makedirs(data)
    subname = quote_plus(base_url)
    subdir = os.path.join(data, subname)
    if not os.path.isdir(subdir):
        os.makedirs(subdir)
    subfile = os.path.join(subdir, filename)
    if not os.path.exists(subfile) and "---" in base_url:
        my_downloads = os.path.expanduser("~/Downloads")
        srcfile = os.path.join(my_downloads, filename)
        if os.path.exists(srcfile):
            shutil.copy(srcfile, subfile)
    if not os.path.exists(subfile):
        logg.info("need %s", subfile)
        try:
            url = base_url + "/" + filename + style
            url = url.replace("/blob/", "/raw/")
            logg.info("curl %s", url)
            urlretrieve(url, subfile)
        except:
            # Ensure zero-length file exists in case we couldn't
            # download the file so that we won't try to
            # re-download it.
            open(subfile, 'a').close()
    if not os.path.exists(subfile):
        return None
    if os.path.getsize(subfile) < 5:
        return None
    #
    if into:
        if not os.path.isdir(into):
            os.makedirs(into)
        intofile = os.path.join(into, filename)
        shutil.copy(subfile, intofile)
        logg.debug("copied %s -> %s", subfile, intofile)
    return filename

def output(cmd: Union[str, List[str]], shell: bool = True) -> str:
    run = subprocess.Popen(cmd, shell=shell, stdout=subprocess.PIPE)
    out, err = run.communicate()
    return out.decode('utf-8')
def grep(pattern: str, lines: Union[str, List[str]]) -> Iterator[str]:
    if isinstance(lines, basestring):
        lines = lines.split("\n")
    for line in lines:
        if re.search(pattern, line.rstrip()):
            yield line.rstrip()
def greps(lines: Union[str, List[str]], pattern: str) -> List[str]:
    return list(grep(pattern, lines))
def all_errors(lines: Union[str, List[str]]) -> Iterator[str]:
    if isinstance(lines, basestring):
        lines = lines.split("\n")
    for line in lines:
        if not line.strip():
            continue
        if "DEBUG:" in line:
            continue
        if "HINT:" in line:
            continue
        yield line.rstrip()
def errors(lines: Union[str, List[str]]) -> List[str]:
    return list(all_errors(lines))

class ZZipTest(unittest.TestCase):
    @property
    def t(self) -> str:
        if not os.path.isdir(testdatadir):
            os.makedirs(testdatadir)
        return testdatadir
    @property
    def s(self) -> str:
        return topsrcdir
    def src(self, name: str) -> str:
        return os.path.join(self.s, name)
    def assertErrorMessage(self, errors: str, errno: int) -> None:
        self.assertIn(': ' + os.strerror(errno), errors)
    def readme(self) -> str:
        f = open(self.src(readme))
        text = f.read()
        f.close()
        return text
    def mkfile(self, name: str, content: str) -> None:
        b = os.path.dirname(name)
        if not os.path.isdir(b):
            os.makedirs(b)
        f = open(name, "w")
        f.write(content)
        f.close()
    def bins(self, name: str) -> str:
        if name == "unzip": return unzip
        if name == "mkzip": return mkzip
        exe = os.path.join(bindir, name)
        if exeext: exe += exeext
        return exe
    def gdb_bins(self, name: str) -> str:
        if name == "unzip": return unzip
        if name == "mkzip": return mkzip
        exe = os.path.join(bindir, ".libs", name)
        if exeext: exe += exeext
        return exe
    def gentext(self, size: int) -> str:
        random.seed(1234567891234567890)
        result = StringIO()
        old1 = ''
        old2 = ''
        for i in range(size):
            while True:
                x = random.choice("       abcdefghijklmnopqrstuvwxyz\n")
                if x == old1 or x == old2: continue
                old1 = old2
                old2 = x
                break
            result.write(x)
        return cast(str, result.getvalue())
    def caller_testname(self) -> str:
        name = get_caller_caller_name()
        x1 = name.find("_")
        if x1 < 0: return name
        x2 = name.find("_", x1 + 1)
        if x2 < 0: return name
        return name[:x2]
    def testname(self, suffix: Optional[str] = None) -> str:
        name = self.caller_testname()
        if suffix:
            return name + "_" + suffix
        return name
    def testzip(self, testname: Optional[str] = None) -> str:
        testname = testname or self.caller_testname()
        zipname = testname + ".zip"
        return zipname
    def testdir(self, testname: Optional[str] = None) -> str:
        testname = testname or self.caller_testname()
        newdir = "tmp." + testname
        if os.path.isdir(newdir):
            shutil.rmtree(newdir)
        os.makedirs(newdir)
        return newdir
    def rm_testdir(self, testname: Optional[str] = None) -> str:
        testname = testname or self.caller_testname()
        newdir = "tmp." + testname
        if os.path.isdir(newdir):
            if KEEP:
                logg.info("KEEP %s", newdir)
            else:
                shutil.rmtree(newdir)
        return newdir
    def rm_testzip(self, testname: Optional[str] = None) -> bool:
        testname = testname or self.caller_testname()
        zipname = testname + ".zip"
        if os.path.exists(zipname):
            if KEEP:
                logg.info("KEEP %s", zipname)
            else:
                os.remove(zipname)
        return True
    ################################################################
    def test_1000_make_test0_zip(self) -> None:
        """ create a test.zip for later tests using standard 'zip'
        It will fall back to a variant in the source code if 'zip'
        is not installed on the build host. The content is just
        the README file that we can check for equality later on. """
        zipfile = "test0.zip"
        tmpdir = "test0.tmp"
        exe = self.bins("mkzip")
        filename = os.path.join(tmpdir, "README")
        filetext = self.readme()
        self.mkfile(filename, filetext)
        shell("{exe} ../{zipfile} README".format(**locals()), cwd=tmpdir)
        self.assertGreater(os.path.getsize(zipfile), 10)
    def test_10001_make_test1_zip(self) -> None:
        """ create a test1.zip for later tests using standard 'zip'
        It will fall back to a variant in the source code if 'zip'
        is not installed on the build host. The archive has 10
        generic files that we can check for their content later. """
        zipfile = "test1.zip"
        tmpdir = "test1.tmp"
        exe = self.bins("mkzip")
        for i in [1, 2, 3, 4, 5, 6, 7, 8, 9]:
            filename = os.path.join(tmpdir, "file.%i" % i)
            filetext = "file-%i\n" % i
            self.mkfile(filename, filetext)
        filename = os.path.join(tmpdir, "README")
        filetext = self.readme()
        self.mkfile(filename, filetext)
        shell("{exe} ../{zipfile} ??*.* README".format(**locals()), cwd=tmpdir)
        self.assertGreater(os.path.getsize(zipfile), 10)
    def test_10002_make_test2_zip(self) -> None:
        """ create a test2.zip for later tests using standard 'zip'
        It will NOT fall back to a variant in the source code.
        The archive has 100 generic files with known content. """
        zipfile = "test2.zip"
        tmpdir = "test2.tmp"
        exe = self.bins("mkzip")
        for i in range(100):
            filename = os.path.join(tmpdir, "file.%02i" % i)
            filetext = "file-%02i\n" % i
            self.mkfile(filename, filetext)
        filename = os.path.join(tmpdir, "README")
        filetext = self.readme()
        self.mkfile(filename, filetext)
        shell("{exe} ../{zipfile} ??*.* README".format(**locals()), cwd=tmpdir)
        self.assertGreater(os.path.getsize(zipfile), 10)
    def test_10003_make_test3_zip(self) -> None:
        """ create a test3.zip for later tests using standard 'zip'
        It will NOT fall back to a variant in the source code.
        The archive has 1000 generic files with known content. """
        zipfile = "test3.zip"
        tmpdir = "test3.tmp"
        exe = self.bins("mkzip")
        for i in range(1000):
            filename = os.path.join(tmpdir, "file.%03i" % i)
            filetext = "file-%03i\n" % i
            self.mkfile(filename, filetext)
        filename = os.path.join(tmpdir, "README")
        filetext = self.readme()
        self.mkfile(filename, filetext)
        shell("{exe} ../{zipfile} ??*.* README".format(**locals()), cwd=tmpdir)
        self.assertGreater(os.path.getsize(zipfile), 10)
    def test_10004_make_test4_zip(self) -> None:
        """ create a test4.zip for later tests using standard 'zip'
        It will NOT fall back to a variant in the source code.
        The archive has 10000 generic files with known content
        and they are stored (NOT compressed) in the archive. """
        zipfile = "test4.zip"
        tmpdir = "test4.tmp"
        exe = self.bins("mkzip")
        for i in range(10000):
            filename = os.path.join(tmpdir, "file%04i.txt" % i)
            filetext = "file-%04i\n" % i
            self.mkfile(filename, filetext)
        filename = os.path.join(tmpdir, "README")
        filetext = self.readme()
        self.mkfile(filename, filetext)
        shell("{exe} -n README ../{zipfile} ??*.* README".format(**locals()), cwd=tmpdir)
        self.assertGreater(os.path.getsize(zipfile), 1000000)
    def test_10005_make_test5_zip(self) -> None:
        """ create a test5.zip for later tests using standard 'zip'
        It will NOT fall back to a variant in the source code.
        The archive has files at multiple subdirectories depth
        and of varying sizes each. """
        zipfile = "test5.zip"
        tmpdir = "test5.tmp"
        exe = self.bins("mkzip")
        for depth in range(20):
            dirpath = ""
            for i in range(depth):
                if i:
                    dirpath += "subdir%i/" % i
            for size in range(18):
                size = 2 ** size
                filetext = self.gentext(size)
                filepart = "file%i-%i.txt" % (depth, size)
                filename = os.path.join(tmpdir, dirpath + filepart)
                self.mkfile(filename, filetext)
        filename = os.path.join(tmpdir, "README")
        filetext = self.readme()
        self.mkfile(filename, filetext)
        shell("{exe} ../{zipfile} -r file* subdir* README".format(**locals()), cwd=tmpdir)
        self.assertGreater(os.path.getsize(zipfile), 1000000)
    def test_10010_make_test0_dat(self) -> None:
        """ create test.dat from test.zip with xorcopy """
        zipfile = "test0.zip"
        datfile = "test0x.dat"
        exe = self.bins("zzxorcopy")
        shell("{exe} {zipfile} {datfile}".format(**locals()))
        self.assertGreater(os.path.getsize(datfile), 10)
        self.assertEqual(os.path.getsize(datfile), os.path.getsize(zipfile))
    def test_10011_make_test1_dat(self) -> None:
        """ create test.dat from test.zip with xorcopy """
        zipfile = "test1.zip"
        datfile = "test1x.dat"
        exe = self.bins("zzxorcopy")
        shell("{exe} {zipfile} {datfile}".format(**locals()))
        self.assertGreater(os.path.getsize(datfile), 10)
        self.assertEqual(os.path.getsize(datfile), os.path.getsize(zipfile))
    def test_10012_make_test2_dat(self) -> None:
        """ create test.dat from test.zip with xorcopy """
        zipfile = "test2.zip"
        datfile = "test2x.dat"
        exe = self.bins("zzxorcopy")
        shell("{exe} {zipfile} {datfile}".format(**locals()))
        self.assertGreater(os.path.getsize(datfile), 10)
        self.assertEqual(os.path.getsize(datfile), os.path.getsize(zipfile))
    def test_10013_make_test3_dat(self) -> None:
        """ create test.dat from test.zip with xorcopy """
        zipfile = "test3.zip"
        datfile = "test3x.dat"
        exe = self.bins("zzxorcopy")
        shell("{exe} {zipfile} {datfile}".format(**locals()))
        self.assertGreater(os.path.getsize(datfile), 10)
        self.assertEqual(os.path.getsize(datfile), os.path.getsize(zipfile))
    def test_10014_make_test4_dat(self) -> None:
        """ create test.dat from test.zip with xorcopy """
        zipfile = "test4.zip"
        datfile = "test4x.dat"
        exe = self.bins("zzxorcopy")
        shell("{exe} {zipfile} {datfile}".format(**locals()))
        self.assertGreater(os.path.getsize(datfile), 10)
        self.assertEqual(os.path.getsize(datfile), os.path.getsize(zipfile))
    def test_20000_zziptest_test0_zip(self) -> None:
        """ run zziptest on test.zip """
        zipfile = "test0.zip"
        logfile = "test0.log"
        exe = self.bins("zziptest")
        shell("{exe} --quick {zipfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
    def test_20001_zziptest_test1_zip(self) -> None:
        """ run zziptest on test.zip """
        zipfile = "test1.zip"
        logfile = "test1.log"
        exe = self.bins("zziptest")
        shell("{exe} --quick {zipfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
    def test_20002_zziptest_test2_zip(self) -> None:
        """ run zziptest on test.zip """
        zipfile = "test2.zip"
        logfile = "test2.log"
        exe = self.bins("zziptest")
        shell("{exe} --quick {zipfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
    def test_20003_zziptest_test3_zip(self) -> None:
        """ run zziptest on test.zip """
        zipfile = "test3.zip"
        logfile = "test3.log"
        exe = self.bins("zziptest")
        shell("{exe} --quick {zipfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
    def test_20004_zziptest_test4_zip(self) -> None:
        """ run zziptest on test.zip """
        zipfile = "test4.zip"
        logfile = "test4.log"
        exe = self.bins("zziptest")
        shell("{exe} --quick {zipfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
    def test_20010_zzcat_test0_zip(self) -> None:
        """ run zzcat on test.zip using just test/README """
        zipfile = "test0.zip"
        getfile = "test0/README"
        logfile = "test0.readme.txt"
        exe = self.bins("zzcat")
        run = shell("{exe} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
    def test_20011_zzcat_test1_zip(self) -> None:
        """ run zzcat on test.zip using just test/README """
        zipfile = "test1.zip"
        getfile = "test1/README"
        logfile = "test1.readme.txt"
        exe = self.bins("zzcat")
        run = shell("{exe} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "test1/file.1"
        run = shell("{exe} {getfile}".format(**locals()))
        self.assertEqual("file-1\n", run.output)
    def test_20012_zzcat_test2_zip(self) -> None:
        """ run zzcat on test.zip using just test/README """
        zipfile = "test2.zip"
        getfile = "test2/README"
        logfile = "test2.readme.txt"
        exe = self.bins("zzcat")
        run = shell("{exe} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "test2/file.22"
        run = shell("{exe} {getfile}".format(**locals()))
        self.assertEqual("file-22\n", run.output)
    def test_20013_zzcat_test3_zip(self) -> None:
        """ run zzcat on test.zip using just test/README """
        zipfile = "test3.zip"
        getfile = "test3/README"
        logfile = "test3.readme.txt"
        exe = self.bins("zzcat")
        run = shell("{exe} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "test3/file.999"
        run = shell("{exe} {getfile}".format(**locals()))
        self.assertEqual("file-999\n", run.output)
    def test_20014_zzcat_test4_zip(self) -> None:
        """ run zzcat on test.zip using just test/README """
        zipfile = "test4.zip"
        getfile = "test4/README"
        logfile = "test4.readme.txt"
        exe = self.bins("zzcat")
        run = shell("{exe} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "test4/file9999.txt"
        run = shell("{exe} {getfile}".format(**locals()))
        self.assertEqual("file-9999\n", run.output)
    def test_20020_zzdir_test0_zip(self) -> None:
        """ run zzdir on test0.zip using just 'test0' """
        zipfile = "test0.zip"
        getfile = "test0"
        exe = self.bins("zzdir")
        run = shell("{exe} {getfile} ".format(**locals()))
        self.assertIn(' README\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertLess(len(run.output), 30)
    def test_20021_zzdir_test1_zip(self) -> None:
        """ run zzdir on test1.zip using just 'test1' """
        zipfile = "test1.zip"
        getfile = "test1"
        exe = self.bins("zzdir")
        run = shell("{exe} {getfile} ".format(**locals()))
        self.assertIn(' file.1\n', run.output)
        self.assertIn(' file.2\n', run.output)
        self.assertIn(' file.9\n', run.output)
        self.assertIn(' README\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20022_zzdir_test2_zip(self) -> None:
        """ run zzdir on test2.zip using just 'test2' """
        zipfile = "test2.zip"
        getfile = "test2"
        exe = self.bins("zzdir")
        run = shell("{exe} {getfile} ".format(**locals()))
        self.assertIn(' file.01\n', run.output)
        self.assertIn(' file.22\n', run.output)
        self.assertIn(' file.99\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20023_zzdir_test3_zip(self) -> None:
        """ run zzdir on test3.zip using just 'test3' """
        zipfile = "test3.zip"
        getfile = "test3"
        exe = self.bins("zzdir")
        run = shell("{exe} {getfile} ".format(**locals()))
        self.assertIn(' file.001\n', run.output)
        self.assertIn(' file.222\n', run.output)
        self.assertIn(' file.999\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20024_zzdir_test4_zip(self) -> None:
        """ run zzdir on test4.zip using just 'test4' """
        zipfile = "test4.zip"
        getfile = "test4"
        exe = self.bins("zzdir")
        run = shell("{exe} {getfile} ".format(**locals()))
        self.assertIn(' file0001.txt\n', run.output)
        self.assertIn(' file2222.txt\n', run.output)
        self.assertIn(' file9999.txt\n', run.output)
        self.assertNotIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20320_zzxordir_test0_dat(self) -> None:
        """ run zzxordir on test0x.dat """
        zipfile = "test0x.dat"
        getfile = "test0x.dat"
        exe = self.bins("zzdir")
        run = shell("{exe} {getfile} ".format(**locals()), returncodes=[0, 66])
        self.assertEqual(run.returncode, 66)
        self.assertEqual("", run.output)
        self.assertIn("did not open test", run.errors)
        exe = self.bins("zzxordir")
        run = shell("{exe} {getfile} ".format(**locals()))
        self.assertIn(' README\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertLess(len(run.output), 30)
    def test_20321_zzxordir_test1_dat(self) -> None:
        """ run zzxordir on test1x.dat using just 'test1x' """
        zipfile = "test1x.dat"
        getfile = "test1x.dat"
        exe = self.bins("zzdir")
        run = shell("{exe} {getfile} ".format(**locals()), returncodes=[0, 66])
        self.assertEqual(run.returncode, 66)
        self.assertEqual("", run.output)
        self.assertIn("did not open test", run.errors)
        exe = self.bins("zzxordir")
        run = shell("{exe} {getfile} ".format(**locals()))
        self.assertIn(' file.1\n', run.output)
        self.assertIn(' file.2\n', run.output)
        self.assertIn(' file.9\n', run.output)
        self.assertIn(' README\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20322_zzxordir_test2_dat(self) -> None:
        """ run zzxordir on test2x.dat using just 'test2x' """
        zipfile = "test2x.dat"
        getfile = "test2x"
        exe = self.bins("zzdir")
        run = shell("{exe} {getfile} ".format(**locals()), returncodes=[0, 66])
        self.assertEqual(run.returncode, 66)
        self.assertEqual("", run.output)
        self.assertIn("did not open test", run.errors)
        exe = self.bins("zzxordir")
        run = shell("{exe} {getfile} ".format(**locals()))
        self.assertIn(' file.01\n', run.output)
        self.assertIn(' file.22\n', run.output)
        self.assertIn(' file.99\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20323_zzxordir_test3_dat(self) -> None:
        """ run zzxordir on test3x.dat using just 'test3x' """
        zipfile = "test3x.dat"
        getfile = "test3x"
        exe = self.bins("zzdir")
        run = shell("{exe} {getfile} ".format(**locals()), returncodes=[0, 66])
        self.assertEqual(run.returncode, 66)
        self.assertEqual("", run.output)
        self.assertIn("did not open test", run.errors)
        exe = self.bins("zzxordir")
        run = shell("{exe} {getfile} ".format(**locals()))
        self.assertIn(' file.001\n', run.output)
        self.assertIn(' file.222\n', run.output)
        self.assertIn(' file.999\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20324_zzxordir_test4_zip(self) -> None:
        """ run zzxordir on test4x.dat using just 'test4x' """
        zipfile = "test4x.dat"
        getfile = "test4x"
        exe = self.bins("zzdir")
        run = shell("{exe} {getfile} ".format(**locals()), returncodes=[0, 66])
        self.assertEqual(run.returncode, 66)
        self.assertEqual("", run.output)
        self.assertIn("did not open test", run.errors)
        exe = self.bins("zzxordir")
        run = shell("{exe} {getfile} ".format(**locals()))
        self.assertIn(' file0001.txt\n', run.output)
        self.assertIn(' file2222.txt\n', run.output)
        self.assertIn(' file9999.txt\n', run.output)
        self.assertNotIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20340_zzxorcat_test0_zip(self) -> None:
        """ run zzxorcat on testx.zip using just testx/README """
        getfile = "test0x/README"
        logfile = "test0x.readme.txt"
        exe = self.bins("zzcat")
        run = shell("{exe} {getfile} ".format(**locals()), lang="C", returncodes=[66])
        self.assertEqual("", run.output)
        self.assertIn("No such file or directory", run.errors)
        exe = self.bins("zzxorcat")
        run = shell("{exe} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
    def test_20341_zzxorcat_test1_zip(self) -> None:
        """ run zzxorcat on testx.zip using just testx/README """
        getfile = "test1x/README"
        logfile = "test1x.readme.txt"
        exe = self.bins("zzcat")
        run = shell("{exe} {getfile} ".format(**locals()), lang="C", returncodes=[66])
        self.assertEqual("", run.output)
        self.assertIn("No such file or directory", run.errors)
        exe = self.bins("zzxorcat")
        run = shell("{exe} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "test1x/file.1"
        run = shell("{exe} {getfile}".format(**locals()))
        self.assertEqual("file-1\n", run.output)
    def test_20342_zzxorcat_test2_zip(self) -> None:
        """ run zzxorcat on testx.zip using just testx/README """
        getfile = "test2x/README"
        logfile = "test2x.readme.txt"
        exe = self.bins("zzcat")
        run = shell("{exe} {getfile} ".format(**locals()), lang="C", returncodes=[66])
        self.assertEqual("", run.output)
        self.assertIn("No such file or directory", run.errors)
        exe = self.bins("zzxorcat")
        run = shell("{exe} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "test2x/file.22"
        run = shell("{exe} {getfile}".format(**locals()))
        self.assertEqual("file-22\n", run.output)
    def test_20343_zzxorcat_test3_zip(self) -> None:
        """ run zzxorcat on testx.zip using just testx/README """
        getfile = "test3x/README"
        logfile = "test3x.readme.txt"
        exe = self.bins("zzcat")
        run = shell("{exe} {getfile} ".format(**locals()), lang="C", returncodes=[66])
        self.assertEqual("", run.output)
        self.assertIn("No such file or directory", run.errors)
        exe = self.bins("zzxorcat")
        run = shell("{exe} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "test3x/file.999"
        run = shell("{exe} {getfile}".format(**locals()))
        self.assertEqual("file-999\n", run.output)
    def test_20344_zzxorcat_test4_zip(self) -> None:
        """ run zzxorcat on testx.zip using just testx/README """
        getfile = "test4x/README"
        logfile = "test4x.readme.txt"
        exe = self.bins("zzxorcat")
        run = shell("{exe} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "test4x/file9999.txt"
        run = shell("{exe} {getfile}".format(**locals()))
        self.assertEqual("file-9999\n", run.output)
    #####################################################################
    # check unzzip
    #####################################################################
    def test_20400_infozip_cat_test0_zip(self) -> None:
        """ run inzo-zip cat test.zip using just archive README """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        zipfile = "test0.zip"
        getfile = "README"
        logfile = "test0.readme.pk.txt"
        exe = self.bins("unzip")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
    def test_20401_infozip_cat_test1_zip(self) -> None:
        """ run info-zip cat test.zip using just archive README """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        zipfile = "test1.zip"
        getfile = "README"
        logfile = "test1.readme.pk.txt"
        exe = self.bins("unzip")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file.1"
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual("file-1\n", run.output)
    def test_20402_infozip_cat_test2_zip(self) -> None:
        """ run info-zip cat test.zip using just archive README """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        zipfile = "test2.zip"
        getfile = "README"
        logfile = "test2.readme.pk.txt"
        exe = self.bins("unzip")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file.22"
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual("file-22\n", run.output)
    def test_20405_zzcat_big_test5_zip(self) -> None:
        """ run info-zip cat test.zip using archive README """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        zipfile = "test5.zip"
        getfile = "README"
        logfile = "test5.readme.pk.txt"
        exe = self.bins("unzip")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "subdir1/subdir2/subdir3/subdir4/subdir5/subdir6/file7-1024.txt"
        compare = self.gentext(1024)
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual(compare, run.output)
    def test_20410_zzcat_big_test0_zip(self) -> None:
        """ run zzcat-big on test.zip using just archive README """
        zipfile = "test0.zip"
        getfile = "README"
        logfile = "test0.readme.big.txt"
        exe = self.bins("unzzip-big")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
    def test_20411_zzcat_big_test1_zip(self) -> None:
        """ run zzcat-big on test.zip using just archive README """
        zipfile = "test1.zip"
        getfile = "README"
        logfile = "test1.readme.big.txt"
        exe = self.bins("unzzip-big")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file.1"
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual("file-1\n", run.output)
    def test_20412_zzcat_big_test2_zip(self) -> None:
        """ run zzcat-seeke on test.zip using just archive README """
        zipfile = "test2.zip"
        getfile = "README"
        logfile = "test2.readme.big.txt"
        exe = self.bins("unzzip-big")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file.22"
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual("file-22\n", run.output)
    def test_20415_zzcat_big_test5_zip(self) -> None:
        """ run zzcat-big on test.zip using archive README """
        zipfile = "test5.zip"
        getfile = "README"
        logfile = "test5.readme.zap.txt"
        exe = self.bins("unzzip-big")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "subdir1/subdir2/subdir3/subdir4/subdir5/subdir6/file7-1024.txt"
        compare = self.gentext(1024)
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual(compare, run.output)
    def test_20420_zzcat_mem_test0_zip(self) -> None:
        """ run zzcat-mem on test.zip using just archive README """
        zipfile = "test0.zip"
        getfile = "README"
        logfile = "test0.readme.mem.txt"
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
    def test_20421_zzcat_mem_test1_zip(self) -> None:
        """ run zzcat-mem on test.zip using archive README """
        zipfile = "test1.zip"
        getfile = "README"
        logfile = "test1.readme.mem.txt"
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -p {zipfile}  {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file.1"
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertEqual("file-1\n", run.output)
    def test_20422_zzcat_mem_test2_zip(self) -> None:
        """ run zzcat-mem on test.zip using archive README """
        zipfile = "test2.zip"
        getfile = "README"
        logfile = "test2.readme.mem.txt"
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file.22"
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual("file-22\n", run.output)
    def test_20423_zzcat_mem_test3_zip(self) -> None:
        """ run zzcat-mem on test.zip using archive README """
        zipfile = "test3.zip"
        getfile = "README"
        logfile = "test3.readme.mem.txt"
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file.999"
        run = shell("{exe} -p {zipfile}  {getfile}".format(**locals()))
        self.assertEqual("file-999\n", run.output)
    def test_20424_zzcat_mem_test4_zip(self) -> None:
        """ run zzcat-mem on test.zip using archive README """
        zipfile = "test4.zip"
        getfile = "README"
        logfile = "test4.readme.mem.txt"
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file9999.txt"
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual("file-9999\n", run.output)
    def test_20425_zzcat_mem_test5_zip(self) -> None:
        """ run zzcat-mem on test.zip using archive README """
        zipfile = "test5.zip"
        getfile = "README"
        logfile = "test5.readme.zap.txt"
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "subdir1/subdir2/subdir3/subdir4/subdir5/subdir6/file7-1024.txt"
        compare = self.gentext(1024)
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual(compare, run.output)
    def test_20430_zzcat_mix_test0_zip(self) -> None:
        """ run zzcat-mix on test.zip using just archive README """
        zipfile = "test0.zip"
        getfile = "README"
        logfile = "test0.readme.mix.txt"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
    def test_20431_zzcat_mix_test1_zip(self) -> None:
        """ run zzcat-mix on test.zip using archive README """
        zipfile = "test1.zip"
        getfile = "README"
        logfile = "test1.readme.mix.txt"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -p {zipfile}  {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file.1"
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertEqual("file-1\n", run.output)
    def test_20432_zzcat_mix_test2_zip(self) -> None:
        """ run zzcat-mix on test.zip using archive README """
        zipfile = "test2.zip"
        getfile = "README"
        logfile = "test2.readme.mix.txt"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file.22"
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual("file-22\n", run.output)
    def test_20433_zzcat_mix_test3_zip(self) -> None:
        """ run zzcat-mix on test.zip using archive README """
        zipfile = "test3.zip"
        getfile = "README"
        logfile = "test3.readme.mix.txt"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file.999"
        run = shell("{exe} -p {zipfile}  {getfile}".format(**locals()))
        self.assertEqual("file-999\n", run.output)
    def test_20434_zzcat_mix_test4_zip(self) -> None:
        """ run zzcat-mix on test.zip using archive README """
        zipfile = "test4.zip"
        getfile = "README"
        logfile = "test4.readme.mix.txt"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file9999.txt"
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual("file-9999\n", run.output)
    def test_20435_zzcat_mix_test5_zip(self) -> None:
        """ run zzcat-mix on test.zip using archive README """
        zipfile = "test5.zip"
        getfile = "README"
        logfile = "test5.readme.zap.txt"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "subdir1/subdir2/subdir3/subdir4/subdir5/subdir6/file7-1024.txt"
        compare = self.gentext(1024)
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual(compare, run.output)
    def test_20440_zzcat_zap_test0_zip(self) -> None:
        """ run zzcat-zap on test.zip using just archive README """
        zipfile = "test0.zip"
        getfile = "README"
        logfile = "test0.readme.txt"
        exe = self.bins("unzzip")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
    def test_20441_zzcat_zap_test1_zip(self) -> None:
        """ run zzcat-zap on test.zip using archive README """
        zipfile = "test1.zip"
        getfile = "README"
        logfile = "test1.readme.zap.txt"
        exe = self.bins("unzzip")
        run = shell("{exe} -p {zipfile}  {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file.1"
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertEqual("file-1\n", run.output)
    def test_20442_zzcat_zap_test2_zip(self) -> None:
        """ run zzcat-zap on test.zip using archive README """
        zipfile = "test2.zip"
        getfile = "README"
        logfile = "test2.readme.zap.txt"
        exe = self.bins("unzzip")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file.22"
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual("file-22\n", run.output)
    def test_20443_zzcat_zap_test3_zip(self) -> None:
        """ run zzcat-zap on test.zip using archive README """
        zipfile = "test3.zip"
        getfile = "README"
        logfile = "test3.readme.zap.txt"
        exe = self.bins("unzzip")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file.999"
        run = shell("{exe} -p {zipfile}  {getfile}".format(**locals()))
        self.assertEqual("file-999\n", run.output)
    def test_20444_zzcat_zap_test4_zip(self) -> None:
        """ run zzcat-zap on test.zip using archive README """
        zipfile = "test4.zip"
        getfile = "README"
        logfile = "test4.readme.zap.txt"
        exe = self.bins("unzzip")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "file9999.txt"
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual("file-9999\n", run.output)
    def test_20445_zzcat_zap_test5_zip(self) -> None:
        """ run zzcat-zap on test.zip using archive README """
        zipfile = "test5.zip"
        getfile = "README"
        logfile = "test5.readme.zap.txt"
        exe = self.bins("unzzip")
        run = shell("{exe} -p {zipfile} {getfile} | tee {logfile}".format(**locals()))
        self.assertGreater(os.path.getsize(logfile), 10)
        self.assertEqual(run.output.split("\n"), self.readme().split("\n"))
        getfile = "subdir1/subdir2/subdir3/subdir4/subdir5/subdir6/file7-1024.txt"
        compare = self.gentext(1024)
        run = shell("{exe} -p {zipfile} {getfile}".format(**locals()))
        self.assertEqual(compare, run.output)

    def test_20500_infozipdir_test0_zip(self) -> None:
        """ run info-zip dir test0.zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        zipfile = "test0.zip"
        getfile = "test0.zip"
        exe = self.bins("unzip")
        run = shell("{exe} -l {getfile} ".format(**locals()))
        self.assertIn(' README\n', run.output)
        self.assertLess(len(run.output), 230)
    def test_20501_infozipdir_test1_zip(self) -> None:
        """ run info-zip dir test1.zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        zipfile = "test1.zip"
        getfile = "test1.zip"
        exe = self.bins("unzip")
        run = shell("{exe} -l {getfile} ".format(**locals()))
        self.assertIn(' file.1\n', run.output)
        self.assertIn(' file.2\n', run.output)
        self.assertIn(' file.9\n', run.output)
        self.assertIn(' README\n', run.output)
    def test_20502_infozipdir_big_test2_zip(self) -> None:
        """ run info-zip dir test2.zip """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        zipfile = "test2.zip"
        getfile = "test2.zip"
        exe = self.bins("unzip")
        run = shell("{exe} -l {getfile} ".format(**locals()))
        self.assertIn(' file.01\n', run.output)
        self.assertIn(' file.22\n', run.output)
        self.assertIn(' file.99\n', run.output)
    def test_20503_infozipdir_big_test3_zip(self) -> None:
        """ run info-zip dir test3.zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        zipfile = "test3.zip"
        getfile = "test3.zip"
        exe = self.bins("unzip")
        run = shell("{exe} -l {getfile} ".format(**locals()))
        self.assertIn(' file.001\n', run.output)
        self.assertIn(' file.222\n', run.output)
        self.assertIn(' file.999\n', run.output)
    def test_20504_infozipdir_big_test4_zip(self) -> None:
        """ run info-zip dir test4.zip """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        zipfile = "test4.zip"
        getfile = "test4.zip"
        exe = self.bins("unzip")
        run = shell("{exe} -l {getfile} ".format(**locals()))
        self.assertIn(' file0001.txt\n', run.output)
        self.assertIn(' file2222.txt\n', run.output)
        self.assertIn(' file9999.txt\n', run.output)
    def test_20505_infozipdir_big_test5_zip(self) -> None:
        """ run info-zip dir on test5.zip """
        zipfile = "test5.zip"
        getfile = "test5.zip"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn('/subdir14/file15-128.txt\n', run.output)
        self.assertIn('/subdir5/subdir6/', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20510_zzdir_big_test0_zip(self) -> None:
        """ run zzdir-big on test0.zip  """
        zipfile = "test0.zip"
        getfile = "test0.zip"
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {getfile} ".format(**locals()))
        self.assertIn(' README\n', run.output)
        self.assertLess(len(run.output), 30)
    def test_20511_zzdir_big_test1_zip(self) -> None:
        """ run zzdir-big on test1.zip  """
        zipfile = "test1.zip"
        getfile = "test1.zip"
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {getfile} ".format(**locals()))
        self.assertIn(' file.1\n', run.output)
        self.assertIn(' file.2\n', run.output)
        self.assertIn(' file.9\n', run.output)
        self.assertIn(' README\n', run.output)
    def test_20512_zzdir_big_test2_zip(self) -> None:
        """ run zzdir-big on test2.zip """
        zipfile = "test2.zip"
        getfile = "test2.zip"
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {getfile} ".format(**locals()))
        self.assertIn(' file.01\n', run.output)
        self.assertIn(' file.22\n', run.output)
        self.assertIn(' file.99\n', run.output)
    def test_20513_zzdir_big_test3_zip(self) -> None:
        """ run zzdir-big on test3.zip  """
        zipfile = "test3.zip"
        getfile = "test3.zip"
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {getfile} ".format(**locals()))
        self.assertIn(' file.001\n', run.output)
        self.assertIn(' file.222\n', run.output)
        self.assertIn(' file.999\n', run.output)
    def test_20514_zzdir_big_test4_zip(self) -> None:
        """ run zzdir-big on test4.zip """
        zipfile = "test4.zip"
        getfile = "test4.zip"
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {getfile} ".format(**locals()))
        self.assertIn(' file0001.txt\n', run.output)
        self.assertIn(' file2222.txt\n', run.output)
        self.assertIn(' file9999.txt\n', run.output)
    def test_20515_zzdir_big_test5_zip(self) -> None:
        """ run zzdir-big on test5.zip """
        zipfile = "test5.zip"
        getfile = "test5.zip"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn('/subdir14/file15-128.txt\n', run.output)
        self.assertIn('/subdir5/subdir6/', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20520_zzdir_mem_test0_zip(self) -> None:
        """ run zzdir-mem on test0.zip  """
        zipfile = "test0.zip"
        getfile = "test0.zip"
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' README\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertLess(len(run.output), 30)
    def test_20521_zzdir_mem_test1_zip(self) -> None:
        """ run zzdir-mem on test1.zip  """
        zipfile = "test1.zip"
        getfile = "test1.zip"
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' file.1\n', run.output)
        self.assertIn(' file.2\n', run.output)
        self.assertIn(' file.9\n', run.output)
        self.assertIn(' README\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20522_zzdir_mem_test2_zip(self) -> None:
        """ run zzdir-mem on test2.zip """
        zipfile = "test2.zip"
        getfile = "test2.zip"
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' file.01\n', run.output)
        self.assertIn(' file.22\n', run.output)
        self.assertIn(' file.99\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20523_zzdir_mem_test3_zip(self) -> None:
        """ run zzdir-mem on test3.zip  """
        zipfile = "test3.zip"
        getfile = "test3.zip"
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' file.001\n', run.output)
        self.assertIn(' file.222\n', run.output)
        self.assertIn(' file.999\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20524_zzdir_mem_test4_zip(self) -> None:
        """ run zzdir-mem on test4.zip """
        zipfile = "test4.zip"
        getfile = "test4.zip"
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' file0001.txt\n', run.output)
        self.assertIn(' file2222.txt\n', run.output)
        self.assertIn(' file9999.txt\n', run.output)
        self.assertNotIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20525_zzdir_mem_test5_zip(self) -> None:
        """ run zzdir-mem on test5.zip """
        zipfile = "test5.zip"
        getfile = "test5.zip"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn('/subdir14/file15-128.txt\n', run.output)
        self.assertIn('/subdir5/subdir6/', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20530_zzdir_mix_test0_zip(self) -> None:
        """ run zzdir-mix on test0.zip  """
        # self.skipTest("todo")
        zipfile = "test0.zip"
        getfile = "test0.zip"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' README\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertLess(len(run.output), 30)
    def test_20531_zzdir_mix_test1_zip(self) -> None:
        """ run zzdir-mix on test1.zip  """
        zipfile = "test1.zip"
        getfile = "test1.zip"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' file.1\n', run.output)
        self.assertIn(' file.2\n', run.output)
        self.assertIn(' file.9\n', run.output)
        self.assertIn(' README\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20532_zzdir_mix_test2_zip(self) -> None:
        """ run zzdir-mix on test2.zip """
        zipfile = "test2.zip"
        getfile = "test2.zip"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' file.01\n', run.output)
        self.assertIn(' file.22\n', run.output)
        self.assertIn(' file.99\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20533_zzdir_mix_test3_zip(self) -> None:
        """ run zzdir-mix on test3.zip  """
        zipfile = "test3.zip"
        getfile = "test3.zip"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' file.001\n', run.output)
        self.assertIn(' file.222\n', run.output)
        self.assertIn(' file.999\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20534_zzdir_mix_test4_zip(self) -> None:
        """ run zzdir-mix on test4.zip """
        zipfile = "test4.zip"
        getfile = "test4.zip"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' file0001.txt\n', run.output)
        self.assertIn(' file2222.txt\n', run.output)
        self.assertIn(' file9999.txt\n', run.output)
        self.assertNotIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20535_zzdir_mix_test5_zip(self) -> None:
        """ run zzdir-mix on test5.zip """
        zipfile = "test5.zip"
        getfile = "test5.zip"
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn('/subdir14/file15-128.txt\n', run.output)
        self.assertIn('/subdir5/subdir6/', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20540_zzdir_zap_test0_zip(self) -> None:
        """ run zzdir-zap on test0.zip  """
        zipfile = "test0.zip"
        getfile = "test0.zip"
        exe = self.bins("unzzip")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' README\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertLess(len(run.output), 30)
    def test_20541_zzdir_zap_test1_zip(self) -> None:
        """ run zzdir-zap on test1.zip  """
        zipfile = "test1.zip"
        getfile = "test1.zip"
        exe = self.bins("unzzip")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' file.1\n', run.output)
        self.assertIn(' file.2\n', run.output)
        self.assertIn(' file.9\n', run.output)
        self.assertIn(' README\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20542_zzdir_zap_test2_zip(self) -> None:
        """ run zzdir-zap on test2.zip """
        zipfile = "test2.zip"
        getfile = "test2.zip"
        exe = self.bins("unzzip")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' file.01\n', run.output)
        self.assertIn(' file.22\n', run.output)
        self.assertIn(' file.99\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20543_zzdir_zap_test3_zip(self) -> None:
        """ run zzdir-zap on test3.zip  """
        zipfile = "test3.zip"
        getfile = "test3.zip"
        exe = self.bins("unzzip")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' file.001\n', run.output)
        self.assertIn(' file.222\n', run.output)
        self.assertIn(' file.999\n', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20544_zzdir_zap_test4_zip(self) -> None:
        """ run zzdir-zap on test4.zip """
        zipfile = "test4.zip"
        getfile = "test4.zip"
        exe = self.bins("unzzip")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn(' file0001.txt\n', run.output)
        self.assertIn(' file2222.txt\n', run.output)
        self.assertIn(' file9999.txt\n', run.output)
        self.assertNotIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20545_zzdir_zap_test5_zip(self) -> None:
        """ run zzdir-zap on test5.zip """
        zipfile = "test5.zip"
        getfile = "test5.zip"
        exe = self.bins("unzzip")
        run = shell("{exe} -v {getfile} ".format(**locals()))
        self.assertIn('/subdir14/file15-128.txt\n', run.output)
        self.assertIn('/subdir5/subdir6/', run.output)
        self.assertIn(' defl:N ', run.output)
        self.assertIn(' stored ', run.output)
    def test_20595_zzextract_zap_test5_zip(self) -> None:
        """ run zzextract-zap on test5.zip 
            => coughs up a SEGFAULT in zzip_dir_close() ?!?"""
        self.rm_testdir()
        zipfile = "test5.zip"
        getfile = "test5.zip"
        tmpdir = self.testdir()
        exe = self.bins("unzzip")
        run = shell("cd {tmpdir} && ../{exe} ../{getfile} ".format(**locals()))
        self.assertTrue(tmpdir + '/subdir1/subdir2/file3-1024.txt')
        # self.rm_testdir()

    url_CVE_2017_5977 = "https://github.com/asarubbo/poc/blob/master"
    zip_CVE_2017_5977 = "00153-zziplib-invalidread-zzip_mem_entry_extra_block"
    def test_59770_infozipdir_CVE_2017_5977(self) -> None:
        """ run info-zip dir test0.zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5977
        file_url = self.url_CVE_2017_5977
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5977 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertIn(" didn't find end-of-central-dir signature at end of central dir", run.errors)
        self.assertIn(" 2 extra bytes at beginning or within zipfile", run.errors)
        self.assertLess(len(run.output), 280)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[2])
        self.assertLess(len(run.output), 101)
        self.assertLess(len(errors(run.errors)), 900)
        self.assertIn('test:  mismatching "local" filename', run.errors)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 0)
        self.rm_testdir()
    def test_59771_zzipdir_big_CVE_2017_5977(self) -> None:
        """ run info-zip -l $(CVE_2017_5977).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5977
        file_url = self.url_CVE_2017_5977
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5977 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" stored test", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 0)
        self.rm_testdir()
    def test_59772_zzipdir_mem_CVE_2017_5977(self) -> None:
        """ run unzzip-mem -l $(CVE_2017_5977).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5977
        file_url = self.url_CVE_2017_5977
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5977 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" 3 test", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 3)
        self.rm_testdir()
    def test_59773_zzipdir_mix_CVE_2017_5977(self) -> None:
        """ run unzzip-mix -l $(CVE_2017_5977).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5977
        file_url = self.url_CVE_2017_5977
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5977 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" 3 test", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 0)
        self.rm_testdir()
    def test_59774_zzipdir_zap_CVE_2017_5977(self) -> None:
        """ run unzzip -l $(CVE_2017_5977).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5977
        file_url = self.url_CVE_2017_5977
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5977 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 255])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" 3 test", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 3)  # TODO
        self.rm_testdir()
    def test_59779(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5977
        file_url = self.url_CVE_2017_5977
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5977 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 163)

    url_CVE_2017_5978 = "https://github.com/asarubbo/poc/blob/master"
    zip_CVE_2017_5978 = "00156-zziplib-oobread-zzip_mem_entry_new"
    def test_59780_infozipdir_CVE_2017_5978(self) -> None:
        """ run info-zip dir test0.zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5978
        file_url = self.url_CVE_2017_5978
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5978 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertIn(' missing 4608 bytes in zipfile', run.errors)
        self.assertIn(' attempt to seek before beginning of zipfile', run.errors)
        self.assertLess(len(run.output), 80)
        self.assertLess(len(errors(run.errors)), 430)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[3])
        self.assertLess(len(run.output), 90)
        self.assertLess(len(errors(run.errors)), 900)
        self.assertIn('attempt to seek before beginning of zipfile', run.errors)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_59781_zzipdir_big_CVE_2017_5978(self) -> None:
        """ run info-zip -l $(CVE_2017_5978).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5978
        file_url = self.url_CVE_2017_5978
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5978 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" stored (null)", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 1])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 0)
        self.rm_testdir()
    def test_59782_zzipdir_mem_CVE_2017_5978(self) -> None:
        """ run unzzip-mem -l $(CVE_2017_5978).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5978
        file_url = self.url_CVE_2017_5978
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5978 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 180)
        # self.assertIn("zzip_mem_disk_load : unable to load entry", run.errors)
        self.assertIn("zzip_mem_disk_open : unable to load disk", run.errors)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 300)
        if grep("DEBUG:", run.errors):
            self.assertIn("zzip_mem_disk_open : unable to load disk", run.errors)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 0)
        self.rm_testdir()
    def test_59783_zzipdir_mix_CVE_2017_5978(self) -> None:
        """ run unzzip-mix -l $(CVE_2017_5978).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5978
        file_url = self.url_CVE_2017_5978
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5978 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 180)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 300)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 0)
        self.rm_testdir()
    def test_59784_zzipdir_zap_CVE_2017_5978(self) -> None:
        """ run unzzip -l $(CVE_2017_5978).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5978
        file_url = self.url_CVE_2017_5978
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5978 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[3])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 180)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 300)
        self.assertTrue(greps(run.errors, "Zipfile corrupted"))
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 0)
        self.rm_testdir()
    def test_59789(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5978
        file_url = self.url_CVE_2017_5978
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5978 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 161)

    url_CVE_2017_5979 = "https://github.com/asarubbo/poc/blob/master"
    zip_CVE_2017_5979 = "00157-zziplib-nullptr-prescan_entry"
    def test_59790_infozipdir_CVE_2017_5979(self) -> None:
        """ run info-zip dir test0.zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5979
        file_url = self.url_CVE_2017_5979
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5979 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertIn(' 1 file', run.output)
        self.assertLess(len(run.output), 330)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 90)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn('extracting: a', run.output)
        self.assertEqual(os.path.getsize(tmpdir + "/a"), 3)
        self.rm_testdir()
    def test_59791_zzipdir_big_CVE_2017_5979(self) -> None:
        """ run info-zip -l $(CVE_2017_5979).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5979
        file_url = self.url_CVE_2017_5979
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5979 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" stored a", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertEqual(os.path.getsize(tmpdir + "/a"), 3)
        self.rm_testdir()
    def test_59792_zzipdir_mem_CVE_2017_5979(self) -> None:
        """ run unzzip-mem -l $(CVE_2017_5979).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5979
        file_url = self.url_CVE_2017_5979
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5979 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" 3 a", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertEqual(os.path.getsize(tmpdir + "/a"), 3)
        self.rm_testdir()
    def test_59793_zzipdir_mix_CVE_2017_5979(self) -> None:
        """ run unzzip-mix -l $(CVE_2017_5979).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5979
        file_url = self.url_CVE_2017_5979
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5979 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" 3 a", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 20)
        self.assertEqual(os.path.getsize(tmpdir + "/a"), 0)    # FIXME
        # self.assertEqual(os.path.getsize(tmpdir+"/a"), 3)  # FIXME
        self.rm_testdir()
    def test_59794_zzipdir_zap_CVE_2017_5979(self) -> None:
        """ run unzzip -l $(CVE_2017_5979).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5979
        file_url = self.url_CVE_2017_5979
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5979 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 255])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" 3 a", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 20)
        self.assertEqual(os.path.getsize(tmpdir + "/a"), 3)
        self.rm_testdir()
    def test_59799(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5979
        file_url = self.url_CVE_2017_5979
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5979 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 155)

    url_CVE_2017_5974 = "https://github.com/asarubbo/poc/blob/master"
    zip_CVE_2017_5974 = "00150-zziplib-heapoverflow-__zzip_get32"
    def test_59740_infozipdir_CVE_2017_5974(self) -> None:
        """ run info-zip dir test0.zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5974
        file_url = self.url_CVE_2017_5974
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5974 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 9])
        self.assertIn(' 1 file', run.output)
        self.assertLess(len(run.output), 330)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 90)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" extracting: test", run.output)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 3)
        self.rm_testdir()
    def test_59741_zzipdir_big_CVE_2017_5974(self) -> None:
        """ run unzzip-big -l $(CVE_2017_5974).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5974
        file_url = self.url_CVE_2017_5974
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5974 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" stored test", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 3)
        self.rm_testdir()
    def test_59742_zzipdir_mem_CVE_2017_5974(self) -> None:
        """ run unzzip-mem -l $(CVE_2017_5974).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5974
        file_url = self.url_CVE_2017_5974
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5974 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" 3 test", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 3)
        self.rm_testdir()
    def test_59743_zzipdir_mix_CVE_2017_5974(self) -> None:
        """ run unzzip-mix -l $(CVE_2017_5974).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5974
        file_url = self.url_CVE_2017_5974
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5974 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" 3 test", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 0)   # FIXME
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3) # FIXME
        self.rm_testdir()
    def test_59744_zzipdir_zap_CVE_2017_5974(self) -> None:
        """ run unzzip -l $(CVE_2017_5974).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5974
        file_url = self.url_CVE_2017_5974
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5974 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 255])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" 3 test", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 3)
        self.rm_testdir()
    def test_59749(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5974
        file_url = self.url_CVE_2017_5974
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5974 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 161)

    url_CVE_2017_5975 = "https://github.com/asarubbo/poc/blob/master"
    zip_CVE_2017_5975 = "00151-zziplib-heapoverflow-__zzip_get64"
    def test_59750_infozipdir_CVE_2017_5975(self) -> None:
        """ run info-zip dir test0.zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5975
        file_url = self.url_CVE_2017_5975
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5975 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertIn(' missing 10 bytes in zipfile', run.errors)
        self.assertIn("didn't find end-of-central-dir signature at end of central dir", run.errors)
        self.assertIn(' 1 file', run.output)
        self.assertLess(len(run.output), 330)
        self.assertLess(len(errors(run.errors)), 430)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[2, 12])
        self.assertLess(len(run.output), 90)
        self.assertLess(len(errors(run.errors)), 900)
        self.assertTrue(any(x in run.errors for x in ('file #1:  bad zipfile offset (local header sig):  127',
                                                      'error: invalid zip file with overlapped components (possible zip bomb)')))
        #self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_59751_zzipdir_big_CVE_2017_5975(self) -> None:
        """ run info-zip -l $(CVE_2017_5975).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5975
        file_url = self.url_CVE_2017_5975
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5975 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" stored test", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 0)  # TODO
        self.rm_testdir()
    def test_59752_zzipdir_mem_CVE_2017_5975(self) -> None:
        """ run unzzip-mem -l $(CVE_2017_5975).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5975
        file_url = self.url_CVE_2017_5975
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5975 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 180)
        self.assertIn("zzip_mem_disk_load : unable to load entry", run.errors)
        self.assertIn("zzip_mem_disk_open : unable to load disk", run.errors)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 200)
        if grep("DEBUG:", run.errors):
            self.assertIn("no header in entry", run.errors)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_59753_zzipdir_mix_CVE_2017_5975(self) -> None:
        """ run unzzip-mix -l $(CVE_2017_5975).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5975
        file_url = self.url_CVE_2017_5975
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5975 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 180)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 200)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_59754_zzipdir_zap_CVE_2017_5975(self) -> None:
        """ run unzzip -l $(CVE_2017_5975).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5975
        file_url = self.url_CVE_2017_5975
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5975 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 180)
        self.assertErrorMessage(run.errors, 0)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 200)
        self.assertTrue(greps(run.errors, "Zipfile corrupted"))
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_59759(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5975
        file_url = self.url_CVE_2017_5975
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5975 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 151)

    url_CVE_2017_5976 = "https://github.com/asarubbo/poc/blob/master"
    zip_CVE_2017_5976 = "00152-zziplib-heapoverflow-zzip_mem_entry_extra_block"
    def test_59760_infozipdir_CVE_2017_5976(self) -> None:
        """ run info-zip dir test0.zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5976
        file_url = self.url_CVE_2017_5976
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5976 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertIn(' 27 extra bytes at beginning or within zipfile', run.errors)
        self.assertIn("didn't find end-of-central-dir signature at end of central dir", run.errors)
        self.assertIn(' 1 file', run.output)
        self.assertLess(len(run.output), 330)
        self.assertLess(len(errors(run.errors)), 500)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[2])
        self.assertLess(len(run.output), 190)
        self.assertLess(len(errors(run.errors)), 900)
        self.assertIn("extracting: test", run.output)
        self.assertIn('-27 bytes too long', run.errors)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 3)
        # self.assertFalse(os.path.exists(tmpdir+"/test"))
        self.rm_testdir()
    def test_59761_zzipdir_big_CVE_2017_5976(self) -> None:
        """ run info-zip -l $(CVE_2017_5976).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5976
        file_url = self.url_CVE_2017_5976
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5976 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" stored test", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 3)
        self.rm_testdir()
    def test_59762_zzipdir_mem_CVE_2017_5976(self) -> None:
        """ run unzzip-mem -l $(CVE_2017_5976).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5976
        file_url = self.url_CVE_2017_5976
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5976 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn("3 test", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 30)  # TODO
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 3)
        self.rm_testdir()
    def test_59763_zzipdir_mix_CVE_2017_5976(self) -> None:
        """ run unzzip-mix -l $(CVE_2017_5976).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5976
        file_url = self.url_CVE_2017_5976
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5976 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn("3 test", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 30)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 0)    # FIXME
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)  # FIXME
        self.rm_testdir()
    def test_59764_zzipdir_zap_CVE_2017_5976(self) -> None:
        """ run unzzip -l $(CVE_2017_5976).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5976
        file_url = self.url_CVE_2017_5976
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5976 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 255])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn("3 test", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 30)
        self.assertEqual(os.path.getsize(tmpdir + "/test"), 3)
        self.rm_testdir()
    def test_59769(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5976
        file_url = self.url_CVE_2017_5976
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5976 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 188)

    url_CVE_2017_5980 = "https://github.com/asarubbo/poc/blob/master"
    zip_CVE_2017_5980 = "00154-zziplib-nullptr-zzip_mem_entry_new"
    def test_59800_infozipdir_CVE_2017_5980(self) -> None:
        """ run info-zip dir test0.zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5980
        file_url = self.url_CVE_2017_5980
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5980 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertIn(' missing 6 bytes in zipfile', run.errors)
        self.assertIn("didn't find end-of-central-dir signature at end of central dir", run.errors)
        self.assertIn(' 1 file', run.output)
        self.assertLess(len(run.output), 330)
        self.assertLess(len(errors(run.errors)), 500)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[3, 12])
        self.assertLess(len(run.output), 90)
        self.assertLess(len(errors(run.errors)), 900)
        self.assertTrue(any(x in run.errors for x in ('file #1:  bad zipfile offset (lseek)',
                                                      'invalid zip file with overlapped components (possible zip bomb)')))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_59801_zzipdir_big_CVE_2017_5980(self) -> None:
        """ run info-zip -l $(CVE_2017_5980).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5980
        file_url = self.url_CVE_2017_5980
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5980 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        self.assertIn(" stored (null)", run.output)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 1])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_59802_zzipdir_mem_CVE_2017_5980(self) -> None:
        """ run unzzip-mem -l $(CVE_2017_5980).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5980
        file_url = self.url_CVE_2017_5980
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5980 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 180)
        self.assertTrue(greps(run.errors, "unable to load disk"))
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 200)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.rm_testdir()
    def test_59803_zzipdir_mix_CVE_2017_5980(self) -> None:
        """ run unzzip-mix -l $(CVE_2017_5980).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5980
        file_url = self.url_CVE_2017_5980
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5980 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[2])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 180)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[2])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 200)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.rm_testdir()
    def test_59804_zzipdir_zap_CVE_2017_5980(self) -> None:
        """ run unzzip -l $(CVE_2017_5980).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5980
        file_url = self.url_CVE_2017_5980
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5980 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[3])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 180)
        self.assertErrorMessage(run.errors, 0)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[3])  # TODO
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 200)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.rm_testdir()
    def test_59809(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5980
        file_url = self.url_CVE_2017_5980
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5980 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 155)

    url_CVE_2017_5981 = "https://github.com/asarubbo/poc/blob/master"
    zip_CVE_2017_5981 = "00161-zziplib-assertionfailure-seeko_C"
    def test_59810_infozipdir_CVE_2017_5981(self) -> None:
        """ run info-zip dir test0.zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5981
        file_url = self.url_CVE_2017_5981
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5981 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertIn(' missing 4 bytes in zipfile', run.errors)
        self.assertIn("zipfile corrupt", run.errors)
        self.assertLess(len(run.output), 80)
        self.assertLess(len(errors(run.errors)), 500)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[3])
        self.assertLess(len(run.output), 90)
        self.assertLess(len(errors(run.errors)), 500)
        self.assertIn('zipfile corrupt.', run.errors)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_59811_zzipdir_big_CVE_2017_5981(self) -> None:
        """ run info-zip -l $(CVE_2017_5981).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5981
        file_url = self.url_CVE_2017_5981
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5981 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_59812_zzipdir_mem_CVE_2017_5981(self) -> None:
        """ run unzzip-mem -l $(CVE_2017_5981).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5981
        file_url = self.url_CVE_2017_5981
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5981 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_59813_zzipdir_mix_CVE_2017_5981(self) -> None:
        """ run unzzip-mix -l $(CVE_2017_5981).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5981
        file_url = self.url_CVE_2017_5981
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5981 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 1)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_59814_zzipdir_zap_CVE_2017_5981(self) -> None:
        """ run unzzip-zap -l $(CVE_2017_5981).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5981
        file_url = self.url_CVE_2017_5981
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5981 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 80)
        self.assertErrorMessage(run.errors, 0)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_59819(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2017_5981
        file_url = self.url_CVE_2017_5981
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2017_5981 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 157)

    url_CVE_2018_10 = "https://github.com/ProbeFuzzer/poc/blob/master/zziplib"
    zip_CVE_2018_10 = "zziplib_0-13-67_zzdir_invalid-memory-access_main.zip"
    def test_63010(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_10
        file_url = self.url_CVE_2018_10
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_10 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 9])
        self.assertIn("End-of-central-directory signature not found", run.errors)
        self.assertLess(len(run.output), 80)
        self.assertLess(len(errors(run.errors)), 600)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[9])
        self.assertLess(len(run.output), 90)
        self.assertLess(len(errors(run.errors)), 600)
        self.assertIn('End-of-central-directory signature not found', run.errors)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63011(self) -> None:
        """ unzzip-big -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_10
        file_url = self.url_CVE_2018_10
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_10 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63012(self) -> None:
        """ unzzip-mem -l $(CVE).zip """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_10
        file_url = self.url_CVE_2018_10
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_10 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63013(self) -> None:
        """ unzzip-mix -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_10
        file_url = self.url_CVE_2018_10
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_10 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 1)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63014(self) -> None:
        """ unzzip-zap -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_10
        file_url = self.url_CVE_2018_10
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_10 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 80)
        self.assertErrorMessage(run.errors, 0)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63018(self) -> None:
        """ zzdir on $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_10
        file_url = self.url_CVE_2018_10
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_10 available: " + filename)
        exe = self.bins("zzdir")
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[66])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 80)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
    def test_63019(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_10
        file_url = self.url_CVE_2018_10
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_10 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 188)

    url_CVE_2018_11 = "https://github.com/ProbeFuzzer/poc/blob/master/zziplib"
    zip_CVE_2018_11 = "zziplib_0-13-67_unzzip_infinite-loop_unzzip_cat_file.zip"
    def test_63110(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_11
        file_url = self.url_CVE_2018_11
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_11 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 9])
        self.assertIn("End-of-central-directory signature not found", run.errors)
        self.assertLess(len(run.output), 90)
        self.assertLess(len(errors(run.errors)), 600)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[9])
        self.assertLess(len(run.output), 90)
        self.assertLess(len(errors(run.errors)), 600)
        self.assertIn('End-of-central-directory signature not found', run.errors)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63111(self) -> None:
        """ unzzip-big -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_11
        file_url = self.url_CVE_2018_11
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_11 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63112(self) -> None:
        """ unzzip-mem -l $(CVE).zip """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_11
        file_url = self.url_CVE_2018_11
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_11 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63113(self) -> None:
        """ unzzip-mix -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_11
        file_url = self.url_CVE_2018_11
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_11 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 1)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63114(self) -> None:
        """ unzzip-zap -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_11
        file_url = self.url_CVE_2018_11
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_11 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 90)
        self.assertErrorMessage(run.errors, 0)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        #
        run = shell("cd {tmpdir} && ../{exe} -p {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.rm_testdir()
    def test_63119(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_11
        file_url = self.url_CVE_2018_11
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_11 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 280)

    url_CVE_2018_12 = "https://github.com/ProbeFuzzer/poc/blob/master/zziplib"
    zip_CVE_2018_12 = "zziplib_0-13-67_unzip-mem_buffer-access-with-incorrect-length-value_zzip_disk_fread.zip"
    def test_63810(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_12
        file_url = self.url_CVE_2018_12
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_12 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[2])
        self.assertIn('reported length of central directory', run.errors)
        self.assertLess(len(run.output), 300)
        self.assertLess(len(errors(run.errors)), 800)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[2])
        self.assertLess(len(run.output), 300)
        self.assertLess(len(errors(run.errors)), 800)
        self.assertIn('reported length of central directory', run.errors)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63811(self) -> None:
        """ unzzip-big -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_12
        file_url = self.url_CVE_2018_12
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_12 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 20)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63812(self) -> None:
        """ unzzip-mem -l $(CVE).zip """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_12
        file_url = self.url_CVE_2018_12
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_12 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertIn("2 aUT", run.output)  # filename contains a control-character
        self.assertGreater(len(run.output), 20)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63813(self) -> None:
        """ unzzip-mix -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_12
        file_url = self.url_CVE_2018_12
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_12 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 1)
        self.assertTrue(grep(run.errors, "central directory not found"))
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63814(self) -> None:
        """ unzzip-zap -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_12
        file_url = self.url_CVE_2018_12
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_12 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 200)
        self.assertErrorMessage(run.errors, 0)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_63819(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_12
        file_url = self.url_CVE_2018_12
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_12 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 141)

    url_CVE_2018_14 = "https://github.com/ProbeFuzzer/poc/blob/master/zziplib"
    zip_CVE_2018_14 = "zziplib_0-13-67_zzdir_memory-alignment-errors___zzip_fetch_disk_trailer.zip"
    def test_64840(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_14
        file_url = self.url_CVE_2018_14
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_14 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[3])
        self.assertIn("attempt to seek before beginning of zipfile", run.errors)
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 800)
        #
        exe = self.bins("unzip")
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[3])
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 800)
        self.assertIn('attempt to seek before beginning of zipfile', run.errors)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_64841(self) -> None:
        """ unzzip-big -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_14
        file_url = self.url_CVE_2018_14
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_14 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_64842(self) -> None:
        """ unzzip-mem -l $(CVE).zip """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_14
        file_url = self.url_CVE_2018_14
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_14 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_64843(self) -> None:
        """ unzzip-mix -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_14
        file_url = self.url_CVE_2018_14
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_14 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 1)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_64844(self) -> None:
        """ unzzip-zap -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_14
        file_url = self.url_CVE_2018_14
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_14 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 200)
        self.assertErrorMessage(run.errors, 0)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_64848(self) -> None:
        """ zzdir $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_14
        file_url = self.url_CVE_2018_14
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_14 available: " + filename)
        exe = self.bins("zzdir")
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[66])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 200)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        self.rm_testdir()
    def test_64849(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_14
        file_url = self.url_CVE_2018_14
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_14 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 56)

    url_CVE_2018_15 = "https://github.com/ProbeFuzzer/poc/blob/master/zziplib"
    zip_CVE_2018_15 = "zziplib_0-13-67_unzip-mem_memory-alignment-errors_zzip_disk_findfirst.zip"
    def test_65400(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_15
        file_url = self.url_CVE_2018_15
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_15 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[2])
        self.assertIn("reported length of central directory", run.errors)
        self.assertLess(len(run.output), 300)
        self.assertLess(len(errors(run.errors)), 800)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[2])
        self.assertLess(len(run.output), 300)
        self.assertLess(len(errors(run.errors)), 800)
        self.assertIn('reported length of central directory', run.errors)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65401(self) -> None:
        """ unzzip-big -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_15
        file_url = self.url_CVE_2018_15
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_15 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 15)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65402(self) -> None:
        """ unzzip-mem -l $(CVE).zip """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_15
        file_url = self.url_CVE_2018_15
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_15 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65403(self) -> None:
        """ unzzip-mix -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_15
        file_url = self.url_CVE_2018_15
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_15 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 1)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65404(self) -> None:
        """ unzzip-zap -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_15
        file_url = self.url_CVE_2018_15
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_15 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 200)
        self.assertErrorMessage(run.errors, 0)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65409(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_15
        file_url = self.url_CVE_2018_15
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_15 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 141)

    url_CVE_2018_16 = "https://github.com/ProbeFuzzer/poc/blob/master/zziplib"
    zip_CVE_2018_16 = "zziplib_0-13-67_unzzip_memory-aligment-errors___zzip_fetch_disk_trailer.zip"
    def test_65410(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_16
        file_url = self.url_CVE_2018_16
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_16 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 9])
        self.assertIn("End-of-central-directory signature not found", run.errors)
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 800)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[9])
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 800)
        self.assertIn('End-of-central-directory signature not found', run.errors)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65411(self) -> None:
        """ unzzip-big -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_16
        file_url = self.url_CVE_2018_16
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_16 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65412(self) -> None:
        """ unzzip-mem -l $(CVE).zip """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_16
        file_url = self.url_CVE_2018_16
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_16 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65413(self) -> None:
        """ unzzip-mix -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_16
        file_url = self.url_CVE_2018_16
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_16 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 1)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65414(self) -> None:
        """ unzzip-zap -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_16
        file_url = self.url_CVE_2018_16
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_16 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 200)
        self.assertErrorMessage(run.errors, 0)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        self.assertTrue(greps(run.errors, "Zipfile corrupted"))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        #
        run = shell("cd {tmpdir} && ../{exe} -p {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertTrue(greps(run.errors, "Zipfile corrupted"))
        self.rm_testdir()
    def test_65419(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_16
        file_url = self.url_CVE_2018_16
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_16 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 124)

    url_CVE_2018_17 = "https://github.com/ProbeFuzzer/poc/blob/master/zziplib"
    zip_CVE_2018_17 = "zziplib_0-13-67_unzip-mem_memory-alignment-errors_zzip_disk_findfirst_64.zip"
    def test_65420(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_17
        file_url = self.url_CVE_2018_17
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_17 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 9])
        self.assertIn("End-of-central-directory signature not found", run.errors)
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 800)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[9])
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 800)
        self.assertIn('End-of-central-directory signature not found', run.errors)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65421(self) -> None:
        """ unzzip-big -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_17
        file_url = self.url_CVE_2018_17
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_17 available: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65422(self) -> None:
        """ unzzip-mem -l $(CVE).zip """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_17
        file_url = self.url_CVE_2018_17
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_17 available: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 50)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        #
        run = shell("cd {tmpdir} && ../{exe} -p {filename} ".format(**locals()),
                    returncodes=[0])
        # self.rm_testdir()
    def test_65423(self) -> None:
        """ unzzip-mix -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_17
        file_url = self.url_CVE_2018_17
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_17 available: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 1)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 30)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65424(self) -> None:
        """ unzzip-zap -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_17
        file_url = self.url_CVE_2018_17
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_17 available: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 200)
        self.assertErrorMessage(run.errors, 0)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 30)
        self.assertTrue(greps(run.errors, "Zipfile corrupted"))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65429(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_17
        file_url = self.url_CVE_2018_17
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_17 available: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 360)

    url_CVE_2018_42 = "https://github.com/fantasy7082/image_test/blob/master"
    zip_CVE_2018_42 = "c006-unknown-add-main"
    def test_65430(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_42
        file_url = self.url_CVE_2018_42
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_42 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[3])
        self.assertIn("missing 18 bytes in zipfile", run.errors)
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 800)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[3, 12])
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 800)
        self.assertIn("missing 18 bytes in zipfile", run.errors)
        self.assertTrue(any(x in run.errors for x in ('expected central file header signature not found',
                                                      'invalid zip file with overlapped components (possible zip bomb)')))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65431(self) -> None:
        """ zzdir $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_42
        file_url = self.url_CVE_2018_42
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_42 available: " + filename)
        exe = self.bins("zzdir")
        run = shell("{exe} {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        logg.info("OUT %s", run.output)
        logg.info("ERR %s", run.errors)
        self.assertIn(" zipped ", run.output)
        self.rm_testdir()

    url_CVE_2018_43 = "https://github.com/fantasy7082/image_test/blob/master"
    zip_CVE_2018_43 = "c008-main-unknown-de"
    def test_65440(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_43
        file_url = self.url_CVE_2018_43
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_43 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[3])
        self.assertIn("missing 18 bytes in zipfile", run.errors)
        self.assertGreater(len(run.output), 30)
        self.assertGreater(len(errors(run.errors)), 1)
        self.assertLess(len(run.output), 500)
        self.assertLess(len(errors(run.errors)), 800)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[3, 12])
        self.assertGreater(len(run.output), 30)
        self.assertGreater(len(errors(run.errors)), 1)
        self.assertLess(len(run.output), 400)
        self.assertLess(len(errors(run.errors)), 800)
        self.assertIn("missing 18 bytes in zipfile", run.errors)
        self.assertTrue(any(x in run.errors for x in ('expected central file header signature not found',
                                                      'invalid zip file with overlapped components (possible zip bomb)')))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65441(self) -> None:
        """ zzdir $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_43
        file_url = self.url_CVE_2018_43
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_43 available: " + filename)
        exe = self.bins("zzdir")
        run = shell("{exe} {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        logg.info("OUT %s", run.output)
        logg.info("ERR %s", run.errors)
        self.assertIn(" zipped ", run.output)
        self.rm_testdir()

    url_CVE_2018_27 = "https://github.com/ret2libc/---provided-by-email---"
    zip_CVE_2018_27 = "poc_bypass_fix2.zip"
    zip_CVE_2018_27_size = 56
    def test_65450(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_27
        file_url = self.url_CVE_2018_27
        filesize = self.zip_CVE_2018_27_size
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_27 available: " + filename)
        if ((os.path.getsize(os.path.join(tmpdir, filename)) != filesize)):
            self.skipTest("zip for CVE_2018_27 is confidential: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 9])
        self.assertIn("End-of-central-directory signature not found", run.errors)
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 800)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[9])
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 800)
        self.assertIn('End-of-central-directory signature not found', run.errors)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65451(self) -> None:
        """ unzzip-big -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_27
        file_url = self.url_CVE_2018_27
        filesize = self.zip_CVE_2018_27_size
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_27 available: " + filename)
        if ((os.path.getsize(os.path.join(tmpdir, filename)) != filesize)):
            self.skipTest("zip for CVE_2018_27 is confidential: " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65452(self) -> None:
        """ unzzip-mem -l $(CVE).zip """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_27
        file_url = self.url_CVE_2018_27
        filesize = self.zip_CVE_2018_27_size
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_27 available: " + filename)
        if ((os.path.getsize(os.path.join(tmpdir, filename)) != filesize)):
            self.skipTest("zip for CVE_2018_27 is confidential: " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 50)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        #
        run = shell("cd {tmpdir} && ../{exe} -p {filename} ".format(**locals()),
                    returncodes=[0])
        # self.rm_testdir()
    def test_65453(self) -> None:
        """ unzzip-mix -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_27
        file_url = self.url_CVE_2018_27
        filesize = self.zip_CVE_2018_27_size
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_27 available: " + filename)
        if ((os.path.getsize(os.path.join(tmpdir, filename)) != filesize)):
            self.skipTest("zip for CVE_2018_27 is confidential: " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 1)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 30)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65454(self) -> None:
        """ unzzip-zap -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_27
        file_url = self.url_CVE_2018_27
        filesize = self.zip_CVE_2018_27_size
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_27 available: " + filename)
        if ((os.path.getsize(os.path.join(tmpdir, filename)) != filesize)):
            self.skipTest("zip for CVE_2018_27 is confidential: " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 200)
        self.assertErrorMessage(run.errors, 0)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 30)
        self.assertTrue(greps(run.errors, "Zipfile corrupted"))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65459(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_27
        file_url = self.url_CVE_2018_27
        filesize = self.zip_CVE_2018_27_size
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_27 available: " + filename)
        if ((os.path.getsize(os.path.join(tmpdir, filename)) != filesize)):
            self.skipTest("zip for CVE_2018_27 is confidential: " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, filesize)  # 56

    url_CVE_2018_41 = "https://github.com/fantasy7082/image_test/blob/master"
    zip_CVE_2018_41 = "c005-bus-zzip_parse_root_directory"  # CVE-2018-7726.
    def test_65460(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_41
        file_url = self.url_CVE_2018_41
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_41 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertIn("missing 20 bytes in zipfile", run.errors)
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 800)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[3])
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 800)
        self.assertIn("missing 20 bytes in zipfile", run.errors)
        self.assertIn('attempt to seek before beginning of zipfile', run.errors)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65461(self) -> None:
        """ zzdir $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_41
        file_url = self.url_CVE_2018_41
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_41 available: " + filename)
        exe = self.bins("zzdir")
        run = shell("{exe} {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[66])
        logg.info("OUT %s", run.output)
        logg.info("ERR %s", run.errors)
        ####### self.assertIn(" zipped ", run.output)
        self.rm_testdir()

    url_CVE_2018_39 = "https://github.com/fantasy7082/image_test/blob/master"
    zip_CVE_2018_39 = "003-unknow-def-zip"
    def test_65470(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_39
        file_url = self.url_CVE_2018_39
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_39 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[3])
        self.assertIn("missing 5123 bytes in zipfile", run.errors)
        self.assertIn("expected central file header signature not found", run.errors)
        self.assertLess(len(run.output), 400)
        self.assertLess(len(errors(run.errors)), 800)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[3, 12])
        self.assertLess(len(run.output), 400)
        self.assertLess(len(errors(run.errors)), 800)
        self.assertIn("missing 5123 bytes in zipfile", run.errors)
        self.assertTrue(any(x in run.errors for x in ('expected central file header signature not found',
                                                      'invalid zip file with overlapped components (possible zip bomb)')))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65471(self) -> None:
        """ unzzip-big -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_39
        file_url = self.url_CVE_2018_39
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_39 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 30)
        self.assertLess(len(errors(run.errors)), 1)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65472(self) -> None:
        """ unzzip-mem -l $(CVE).zip """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_39
        file_url = self.url_CVE_2018_39
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_39 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 200)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        #
        run = shell("cd {tmpdir} && ../{exe} -p {filename} ".format(**locals()),
                    returncodes=[0])
        # self.rm_testdir()
    def test_65473(self) -> None:
        """ unzzip-mix -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_39
        file_url = self.url_CVE_2018_39
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_39 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 1)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 30)
        self.assertErrorMessage(run.errors, errno.EILSEQ)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65474(self) -> None:
        """ unzzip-zap -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_39
        file_url = self.url_CVE_2018_39
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_39 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 1)
        self.assertLess(len(errors(run.errors)), 200)
        self.assertErrorMessage(run.errors, 0)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 3])
        self.assertLess(len(run.output), 30)
        self.assertTrue(greps(run.errors, "Zipfile corrupted"))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65479(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_39
        file_url = self.url_CVE_2018_39
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_39 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 82347)

    url_CVE_2018_40 = "https://github.com/fantasy7082/image_test/blob/master"
    zip_CVE_2018_40 = "002-mem-leaks-zip"
    def test_65480(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_40
        file_url = self.url_CVE_2018_40
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_40 available: " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[3])
        self.assertIn("missing 21 bytes in zipfile", run.errors)
        self.assertGreater(len(run.output), 20)
        self.assertGreater(len(errors(run.errors)), 1)
        self.assertLess(len(run.output), 2500)
        self.assertLess(len(errors(run.errors)), 800)
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[3, 12])
        self.assertGreater(len(run.output), 20)
        self.assertGreater(len(errors(run.errors)), 1)
        self.assertLess(len(run.output), 2500)
        self.assertLess(len(errors(run.errors)), 800)
        self.assertIn("missing 21 bytes in zipfile", run.errors)
        self.assertTrue(any(x in run.errors for x in ('expected central file header signature not found',
                                                      'invalid zip file with overlapped components (possible zip bomb)')))
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        self.rm_testdir()
    def test_65482(self) -> None:
        """ unzzip-mem -l $(CVE).zip """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_40
        file_url = self.url_CVE_2018_40
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_40 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1500)
        self.assertLess(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1500)
        self.assertLess(len(errors(run.errors)), 10)
        # self.assertEqual(os.path.getsize(tmpdir+"/test"), 3)
        self.assertFalse(os.path.exists(tmpdir + "/test"))
        #
        run = shell("cd {tmpdir} && ../{exe} -p {filename} ".format(**locals()),
                    returncodes=[0])
        self.rm_testdir()

    url_CVE_2018_17828 = "https://github.com/gdraheim/zziplib/files/2415382"
    zip_CVE_2018_17828 = "evil.zip"
    def test_65484(self) -> None:
        """ extract file with "../" in the pathname [CVE-2018-17828] """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2018_17828
        file_url = self.url_CVE_2018_17828
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_40 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0, 80])
        self.assertLess(len(run.output), 500)
        self.assertLess(len(errors(run.errors)), 1)
        #
        workdir = tmpdir + "/d1/d2"
        os.makedirs(workdir)
        run = shell("cd {workdir} && ../../../{exe} ../../{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 500)
        self.assertEqual(len(errors(run.errors)), 1)
        self.assertFalse(os.path.exists(tmpdir + "/test/evil.conf"))
        self.assertTrue(os.path.exists(workdir + "/test/evil.conf"))
        self.rm_testdir()

    def test_65485_list_verbose_compressed_with_directory(self) -> None:
        """ verbously list a zipfile containing directories """
        chdir = "chdir"
        if not exeext: chdir = "cd"
        tmpdir = self.testdir()
        workdir = tmpdir + "/d"
        zipname = "ZIPfile"
        os.makedirs(workdir)
        f = open(tmpdir + "/d/file", "w+")
        for i in range(10):
            f.write("This is line %d\r\n" % (i + 1))
        f.close()
        # create the ZIPfile
        mkzip = self.bins("mkzip")
        run = shell("{chdir} {tmpdir} &&  {mkzip} -9 {zipname}.zip d".format(**locals()))
        self.assertFalse(run.returncode)
        run = shell("{chdir} {tmpdir} && unzip -v {zipname}.zip".format(**locals()))
        logg.info("unzip \n%s", run.output)
        # list the ZIPfile
        exe = self.bins("unzip-mem")
        run = shell("{chdir} {tmpdir} && ../{exe} -v {zipname}.zip".format(**locals()), returncodes=[0])
        self.assertFalse(run.returncode)
        self.assertIn("d/", run.output)
        self.rm_testdir()

    def test_65486_list_verbose_compressed_with_directory(self) -> None:
        """ verbously list a zipfile containing directories """
        chdir = "chdir"
        if not exeext: chdir = "cd"
        tmpdir = self.testdir()
        workdir = tmpdir + "/d"
        zipname = "ZIPfile"
        os.makedirs(workdir)
        f = open(tmpdir + "/d/file", "w+")
        for i in range(10):
            f.write("This is line %d\r\n" % (i + 1))
        f.close()
        # create the ZIPfile
        mkzip = self.bins("mkzip")
        run = shell("{chdir} {tmpdir} &&  {mkzip} -9r {zipname}.zip d".format(**locals()))
        self.assertFalse(run.returncode)
        run = shell("{chdir} {tmpdir} && unzip -v {zipname}.zip".format(**locals()))
        logg.info("unzip \n%s", run.output)
        # list the ZIPfile
        exe = self.bins("unzip-mem")
        run = shell("{chdir} {tmpdir} && ../{exe} -v {zipname}.zip".format(**locals()), returncodes=[0])
        self.assertFalse(run.returncode)
        self.assertIn("d/file", run.output)
        self.rm_testdir()

    url_CVE_2020_04 = "https://github.com/gdraheim/zziplib/files/5340201"
    zip_CVE_2020_04 = "2020_10_OutagesPUReasons.zip"
    def test_65570(self) -> None:
        """ info unzip -l $(CVE).zip = ZIP64 support with contained file size > 2G  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2020_04
        file_url = self.url_CVE_2020_04
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2018_39 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[0])
        self.assertTrue(os.path.exists(tmpdir + "/2020_10_OutagesPUReasons.csv"))
        self.assertEqual(os.path.getsize(tmpdir + "/2020_10_OutagesPUReasons.csv"), 2590160)
        self.rm_testdir()
    def test_65571(self) -> None:
        """ unzzip-big -l $(CVE).zip = ZIP64 support with contained file size > 2G  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2020_04
        file_url = self.url_CVE_2020_04
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2020_04 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertTrue(os.path.exists(tmpdir + "/2020_10_OutagesPUReasons.csv"))
        self.assertEqual(os.path.getsize(tmpdir + "/2020_10_OutagesPUReasons.csv"), 2590160)
        self.rm_testdir()
    def test_65572(self) -> None:
        """ unzzip-mem -l $(CVE).zip = ZIP64 support with contained file size > 2G """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2020_04
        file_url = self.url_CVE_2020_04
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2020_04 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertTrue(os.path.exists(tmpdir + "/2020_10_OutagesPUReasons.csv"))
        self.assertEqual(os.path.getsize(tmpdir + "/2020_10_OutagesPUReasons.csv"), 2590160)
        #
        run = shell("cd {tmpdir} && ../{exe} -p {filename} ".format(**locals()),
                    returncodes=[0])
        self.rm_testdir()
    def test_65573(self) -> None:
        """ unzzip-mix -l $(CVE).zip = ZIP64 support with contained file size > 2G  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2020_04
        file_url = self.url_CVE_2020_04
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2020_04 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        self.assertLess(len(run.output), 30)
        self.assertTrue(os.path.exists(tmpdir + "/2020_10_OutagesPUReasons.csv"))
        self.assertEqual(os.path.getsize(tmpdir + "/2020_10_OutagesPUReasons.csv"), 2590160)
        self.rm_testdir()
    def test_65574(self) -> None:
        """ unzzip-zap -l $(CVE).zip = ZIP64 support with contained file size > 2G """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2020_04
        file_url = self.url_CVE_2020_04
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2020_04 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertTrue(os.path.exists(tmpdir + "/2020_10_OutagesPUReasons.csv"))
        self.assertEqual(os.path.getsize(tmpdir + "/2020_10_OutagesPUReasons.csv"), 2590160)
        self.rm_testdir()
    def test_65579(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2020_04
        file_url = self.url_CVE_2020_04
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2020_04 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 171344)

    url_CVE_2019_69 = "https://github.com/gdraheim/zziplib/files/3001317"
    zip_CVE_2019_69 = "zip_poc.zip"
    def test_65670(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2019_69
        file_url = self.url_CVE_2019_69
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2019_69 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[2])
        self.assertTrue(greps(run.errors, "missing 6 bytes in zipfile"))
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[3, 12])
        self.rm_testdir()
    def test_65671(self) -> None:
        """ unzzip-big -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2019_69
        file_url = self.url_CVE_2019_69
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2019_69 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[1])
        self.rm_testdir()
    def test_65672(self) -> None:
        """ unzzip-mem -l $(CVE).zip """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2019_69
        file_url = self.url_CVE_2019_69
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2019_69 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        # self.assertLess(len(run.output), 1)
        # self.assertEqual(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} -p {filename} ".format(**locals()),
                    returncodes=[0])
        self.rm_testdir()
    def test_65673(self) -> None:
        """ unzzip-mix -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2019_69
        file_url = self.url_CVE_2019_69
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2019_69 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[2])
        self.assertTrue(greps(run.errors, "Invalid or incomplete") or greps(run.errors, "Illegal byte sequence"))
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[2])
        # self.assertLess(len(run.output), 30)
        self.assertTrue(greps(run.errors, "Invalid or incomplete") or greps(run.errors, "Illegal byte sequence"))
        self.rm_testdir()
    def test_65674(self) -> None:
        """ unzzip-zap -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2019_69
        file_url = self.url_CVE_2019_69
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2019_69 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[3])
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[3])
        self.assertTrue(greps(run.errors, "Zipfile corrupted"))
        self.rm_testdir()
    def test_65679(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2019_69
        file_url = self.url_CVE_2019_69
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2019_69 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 155)

    url_CVE_2019_70 = "https://github.com/gdraheim/zziplib/files/3006594"
    zip_CVE_2019_70 = "POC.zip"
    def test_65770(self) -> None:
        """ info unzip -l $(CVE).zip  """
        if unzip_skip: self.skipTest("skip tests using infozip 'unzip'")
        tmpdir = self.testdir()
        filename = self.zip_CVE_2019_70
        file_url = self.url_CVE_2019_70
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2019_70 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        #
        run = shell("cd {tmpdir} && {exe} -o {filename}".format(**locals()),
                    returncodes=[0])
        self.assertEqual(os.path.getsize(tmpdir + "/POC1"), 135)
        self.assertEqual(os.path.getsize(tmpdir + "/POC2"), 135)
        self.assertEqual(os.path.getsize(tmpdir + "/POC3"), 303)
        self.rm_testdir()
    def test_65771(self) -> None:
        """ unzzip-big -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2019_70
        file_url = self.url_CVE_2019_70
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2019_70 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-big")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertEqual(os.path.getsize(tmpdir + "/POC1"), 135)
        self.assertEqual(os.path.getsize(tmpdir + "/POC2"), 135)
        self.assertEqual(os.path.getsize(tmpdir + "/POC3"), 303)
        self.rm_testdir()
    def test_65772(self) -> None:
        """ unzzip-mem -l $(CVE).zip """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2019_70
        file_url = self.url_CVE_2019_70
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2019_70 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-mem")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        # self.assertLess(len(run.output), 1)
        # self.assertEqual(len(errors(run.errors)), 1)
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertLess(len(run.output), 1)
        self.assertEqual(os.path.getsize(tmpdir + "/POC1"), 135)
        self.assertEqual(os.path.getsize(tmpdir + "/POC2"), 135)
        self.assertEqual(os.path.getsize(tmpdir + "/POC3"), 303)
        #
        run = shell("cd {tmpdir} && ../{exe} -p {filename} ".format(**locals()),
                    returncodes=[0])
        self.rm_testdir()
    def test_65773(self) -> None:
        """ unzzip-mix -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2019_70
        file_url = self.url_CVE_2019_70
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2019_70 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip-mix")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        self.assertFalse(os.path.exists((tmpdir + "/POC1")))
        self.assertFalse(os.path.exists((tmpdir + "/POC2")))
        self.assertFalse(os.path.exists((tmpdir + "/POC3")))
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0, 2])
        # self.assertLess(len(run.output), 30)
        self.assertEqual(os.path.getsize(tmpdir + "/POC1"), 135)
        self.assertEqual(os.path.getsize(tmpdir + "/POC2"), 135)
        self.assertEqual(os.path.getsize(tmpdir + "/POC3"), 303)
        self.rm_testdir()
    def test_65774(self) -> None:
        """ unzzip-zap -l $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2019_70
        file_url = self.url_CVE_2019_70
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2019_70 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} -l {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        #
        run = shell("cd {tmpdir} && ../{exe} {filename} ".format(**locals()),
                    returncodes=[0])
        self.assertEqual(os.path.getsize(tmpdir + "/POC1"), 135)
        self.assertEqual(os.path.getsize(tmpdir + "/POC2"), 135)
        self.assertEqual(os.path.getsize(tmpdir + "/POC3"), 303)
        self.rm_testdir()
    def test_65779(self) -> None:
        """ check $(CVE).zip  """
        tmpdir = self.testdir()
        filename = self.zip_CVE_2019_70
        file_url = self.url_CVE_2019_70
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_CVE_2019_70 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        shell("ls -l {tmpdir}/{filename}".format(**locals()))
        size = os.path.getsize(os.path.join(tmpdir, filename))
        self.assertEqual(size, 771)
    url_BUG_143 = "https://github.com/gdraheim/zziplib/files/9757091"
    zip_BUG_143 = "zip.c_347_44-in-__zzip_fetch_disk_trailer.zip"
    def test_70143(self) -> None:
        """ check github issue #143 - requires `make fortify`"""
        tmpdir = self.testdir()
        filename = self.zip_BUG_143
        file_url = self.url_BUG_143
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_BUG_143 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("zzdir")
        run = shell("{exe} {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        #
    url_BUG_144 = "https://github.com/gdraheim/zziplib/files/9757121"
    zip_BUG_144 = "zip.c_347_44-in-__zzip_fetch_disk_trailer.zip"
    def test_70144(self) -> None:
        """ check github issue #144 - requires `make fortify`"""
        tmpdir = self.testdir()
        filename = self.zip_BUG_144
        file_url = self.url_BUG_144
        if not download_raw(file_url, filename, tmpdir):
            self.skipTest("no zip_BUG_144 available: " + filename)
        if not os.path.isfile(os.path.join(tmpdir, filename)): self.skipTest("missing " + filename)
        exe = self.bins("unzzip")
        run = shell("{exe} {tmpdir}/{filename} ".format(**locals()),
                    returncodes=[0])
        #

    def test_81000_zzshowme_check_sfx(self) -> None:
        """ create an *.exe that can extract its own zip content """
        mkzip = self.bins("mkzip")
        exefile = "tmp.zzshowme" + exeext
        libstub1 = ".libs/zzipself" + exeext
        libstub2 = "zzipself" + exeext
        libstub = os.path.exists(libstub1) and libstub1 or libstub2
        txtfile_name = readme
        txtfile = self.src(readme)
        # add the extract-stub so we have reserved the size
        run = shell("{mkzip} -0 -j {exefile}.zip {libstub}".format(**locals()))
        self.assertFalse(run.returncode)
        # add the actual content which may now be compressed
        run = shell("{mkzip} -9 -j {exefile}.zip {txtfile}".format(**locals()))
        self.assertFalse(run.returncode)
        # rename .zip to .exe and put the extract-stub at the start
        shutil.copy(exefile + ".zip", exefile)
        setstub = "./zzipsetstub" + exeext
        run = shell("{setstub} {exefile} {libstub}".format(**locals()))
        self.assertFalse(run.returncode)
        os.chmod(exefile, 0o755)
        # now ask the new .exe to show some of its own content
        run = shell("./{exefile} {txtfile_name}".format(**locals()))
        self.assertFalse(run.returncode)
        txt = open(txtfile).read()
        self.assertEqual(txt.split("\n"), run.output.split("\n"))

    def test_89000_make_test1w_zip(self) -> None:
        """ create a test1w.zip using zzip/write functions. """
        exe = self.bins("zzip")
        run = shell("{exe} --version".format(**locals()))
        if "- NO -" in run.output:
            self.skipTest("- NO -D_ZZIP_ENABLE_WRITE")
            return
        zipfile = self.testzip()
        tmpdir = self.testdir()
        exe = self.bins("zzip")
        for i in [1, 2, 3, 4, 5, 6, 7, 8, 9]:
            filename = os.path.join(tmpdir, "file.%i" % i)
            filetext = "file-%i\n" % i
            self.mkfile(filename, filetext)
        filename = os.path.join(tmpdir, "README")
        filetext = self.readme()
        self.mkfile(filename, filetext)
        self.rm_testzip()
        shell("../{exe} ../{zipfile} ??*.* README".format(**locals()), cwd=tmpdir)
        self.assertGreater(os.path.getsize(zipfile), 10)


if __name__ == "__main__":
    import optparse
    _o = optparse.OptionParser("%prog [options] test_xxx")
    _o.add_option("-D", "--downloadonly", action="store_true", default=downloadonly,
                  help="setup helper: get downloads only [%default]")
    _o.add_option("-d", "--downloaddir", metavar="DIR", default=downloaddir,
                  help="put and get downloads from here [%default]")
    _o.add_option("-n", "--nodownloads", action="store_true", default=nodownloads,
                  help="no downloads / skipping CVE zip file tests [%default]")
    _o.add_option("--downloads", metavar="YES", default="")
    _o.add_option("-b", "--bindir", metavar="DIR", default=bindir,
                  help="path to the bindir to use [%default]")
    _o.add_option("-s", "--topsrcdir", metavar="DIR", default=topsrcdir,
                  help="path to the top srcdir / unpack directory [%default]")
    _o.add_option("-t", "--testdatadir", metavar="DIR", default=testdatadir,
                  help="path where temporary testdata is created [%default]")
    _o.add_option("-Z", "--mkzip", metavar="EXE", default=mkzip,
                  help="name or path to zip.exe for *.zip creation [%default]")
    _o.add_option("-U", "--unzip", metavar="EXE", default=unzip,
                  help="name or path to unzip.exe to unpack *.zip [%default]")
    _o.add_option("-E", "--exeext", metavar="EXT", default=exeext,
                  help="the executable extension (automake $(EXEEXT)) [%default]")
    _o.add_option("-K", "--keep", action="store_true", default=KEEP,
                  help="Keep test data around. [%default]")
    _o.add_option("--failfast", action="store_true", default=False,
                  help="Stop the test run on the first error or failure. [%default]")
    _o.add_option("--xmlresults", metavar="FILE", default=None,
                  help="capture results as a junit xml file [%default]")
    _o.add_option("-v", "--verbose", action="count", default=0,
                  help="increase logging output [%default]")
    opt, args = _o.parse_args()
    logging.basicConfig(level=logging.WARNING - 10 * opt.verbose)
    downloadonly = opt.downloadonly
    downloaddir = opt.downloaddir
    nodownloads = yesno(opt.nodownloads)
    if opt.downloads:
        nodownloads = not yesno(opt.downloads)
    topsrcdir = opt.topsrcdir
    bindir = opt.bindir
    testdatdir = opt.testdatadir
    KEEP = opt.keep
    if opt.mkzip.endswith("-NOTFOUND"):
        logg.error("  no infozip 'zip' found, expect failing tests (given -Z %s)", opt.mkzip)
    else:
        mkzip = opt.mkzip
    if opt.unzip.endswith("-NOTFOUND") or len(opt.unzip) < 3:
        logg.error("no infozip 'unzip' found, expect skipped tests (given -U %s)", opt.unzip)
        unzip_skip = True
    else:
        unzip = opt.unzip
    exeext = opt.exeext
    #
    if downloadonly:
        downloads = 0
        for classname in sorted(list(globals())):
            if not classname.endswith("Test"):
                continue
            testclass = globals()[classname]
            for item in sorted(dir(testclass)):
                if item.startswith("url_"):
                    name = item.replace("url_", "zip_")
                    if name in testclass.__dict__:
                        url = testclass.__dict__[item]
                        zip = testclass.__dict__[name]
                        download(url, zip)
                        downloads += 1
        if downloads:
            sys.exit(0)
        logg.error("could not download any file")
        sys.exit(1)
    #
    if not args: args += ["test_"]
    suite = unittest.TestSuite()
    for arg in args:
        for classname in sorted(list(globals())):
            if not classname.endswith("Test"):
                continue
            testclass = globals()[classname]
            for method in sorted(dir(testclass)):
                if "*" not in arg: arg += "*"
                if len(arg) > 2 and arg[1] == "_":
                    arg = "test" + arg[1:]
                if matches(method, arg):
                    suite.addTest(testclass(method))
    # select runner
    xmlresults = None
    if opt.xmlresults:
        if os.path.exists(opt.xmlresults):
            os.remove(opt.xmlresults)
        xmlresults = open(opt.xmlresults, "wb")
        logg.info("xml results into %s", opt.xmlresults)
    if xmlresults:
        import xmlrunner  # type: ignore
        Runner = xmlrunner.XMLTestRunner
        result = Runner(xmlresults).run(suite)
    else:
        Runner = unittest.TextTestRunner
        result = Runner(verbosity=opt.verbose, failfast=opt.failfast).run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
