"""Focused real-launch resolver tests without unrelated orchestration imports."""
import ast
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import venv

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'src/presentation_agent/deckcompiler/orchestration/vector_preflight.py'
ERRORS=ROOT/'src/presentation_agent/deckcompiler/errors.py'

def resolver(path):
    # Compile the exact production function and its real error factory only.
    # This is not a full public preflight integration test.
    namespace={'Path':Path,'shutil':shutil}
    exec(compile(ERRORS.read_text(),str(ERRORS),'exec'),namespace)
    tree=ast.parse(path.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_resolve_python_executable','_error')]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
    return namespace['_resolve_python_executable'],namespace['DeckCompilerError']

@contextmanager
def cwd(path):
    old=Path.cwd();os.chdir(path)
    try:yield
    finally:os.chdir(old)

class PythonResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resolve=staticmethod(resolver(SOURCE)[0]);cls.error=resolver(SOURCE)[1]
        cls.tmp=tempfile.TemporaryDirectory(prefix='resolver-test-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root=Path(cls.tmp.name);cls.env=cls.root/'external venv'
        venv.EnvBuilder(with_pip=False,symlinks=True).create(cls.env)
        cls.python=cls.env/'bin/python'
        if os.name=='nt':cls.python=cls.env/'Scripts/python.exe'
        probe=subprocess.run([str(cls.python),'-I','-c','import sysconfig;print(sysconfig.get_path("purelib"))'],check=True,capture_output=True,text=True)
        cls.site=Path(probe.stdout.strip());(cls.site/'resolver_local_marker.py').write_text('VALUE="venv-only"\n')
    def test_real_venv_launch_preserves_site_packages(self):
        selected=self.resolve(str(self.python));self.assertEqual(selected,self.python.absolute().as_posix())
        p=subprocess.run([selected,'-I','-c','import json,sys,resolver_local_marker;print(json.dumps([sys.prefix,sys.base_prefix,resolver_local_marker.VALUE]))'],check=True,capture_output=True,text=True)
        prefix,base,value=json.loads(p.stdout);self.assertEqual(Path(prefix),self.env);self.assertNotEqual(prefix,base);self.assertEqual(value,'venv-only')
    def test_relative_path_preserved(self):
        with cwd(self.root):self.assertEqual(self.resolve(str(self.python.relative_to(self.root))),self.python.absolute().as_posix())
    def test_path_search_preserves_symlink(self):
        with patch.dict(os.environ,{'PATH':str(self.python.parent)}):self.assertEqual(self.resolve(self.python.name),self.python.absolute().as_posix())
    def test_relative_path_search(self):
        with cwd(self.root),patch.dict(os.environ,{'PATH':str(self.python.parent.relative_to(self.root))}):self.assertEqual(self.resolve(self.python.name),self.python.absolute().as_posix())
    def test_home_expansion(self):
        # Windows expanduser uses USERPROFILE; POSIX uses HOME.
        home_key = 'USERPROFILE' if os.name == 'nt' else 'HOME'
        with patch.dict(os.environ,{home_key:str(self.root)}):self.assertEqual(self.resolve('~/'+str(self.python.relative_to(self.root))),self.python.absolute().as_posix())
    def test_missing_directory_broken_link_rejected(self):
        link=self.root/'broken';link.symlink_to(self.root/'not-present')
        for path in [self.root/'missing',self.root,link]:
            with self.subTest(path=path),self.assertRaises(Exception) as raised:self.resolve(str(path))
            self.assertEqual(raised.exception.code,'DC_VECTOR_PREFLIGHT_PYTHON_MISSING')
    def test_existing_regular_file_behavior_unchanged(self):
        # Existing resolver checks is_file, not executable permission. Do not
        # silently expand this narrow bug fix into a permission-policy change.
        p=self.root/'ordinary-file';p.write_text('not executed')
        self.assertEqual(self.resolve(str(p)),p.absolute().as_posix())
    def test_symlink_parent_dotdot_not_canonicalized(self):
        actual=self.root/'actual';actual.mkdir();link=self.root/'alias';link.symlink_to(actual,target_is_directory=True)
        p=link/'..'/self.python.relative_to(self.root)
        self.assertTrue(p.is_file());self.assertEqual(self.resolve(str(p)),p.absolute().as_posix());self.assertIn('/../',self.resolve(str(p)))

if __name__=='__main__':unittest.main(verbosity=2)
