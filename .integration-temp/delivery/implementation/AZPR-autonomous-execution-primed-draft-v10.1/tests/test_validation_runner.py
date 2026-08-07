from __future__ import annotations
import importlib.util
import os
import tempfile
import subprocess
import unittest
import sys
from pathlib import Path

PACK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACK/'trusted-validation-runner'))
spec=importlib.util.spec_from_file_location('trusted_validation_runner',PACK/'trusted-validation-runner'/'trusted_validation_runner.py')
assert spec and spec.loader
runner=importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)

def init_commit(repo: Path) -> None:
    subprocess.run(['/usr/bin/git','init','-q'],cwd=repo,check=True)
    subprocess.run(['/usr/bin/git','config','user.email','security-test@azpr.local'],cwd=repo,check=True)
    subprocess.run(['/usr/bin/git','config','user.name','AZPR Security Test'],cwd=repo,check=True)
    (repo/'baseline.txt').write_text('baseline')
    subprocess.run(['/usr/bin/git','add','baseline.txt'],cwd=repo,check=True)
    subprocess.run(['/usr/bin/git','commit','-q','-m','baseline'],cwd=repo,check=True)

class ValidationRunnerTests(unittest.TestCase):
    def test_snapshot_is_read_only_and_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); repo=root/'repo'; snap=root/'snap'; repo.mkdir(); snap.mkdir(); init_commit(repo)
            (repo/'a.txt').write_text('a')
            tree=runner.snapshot_repository(repo,snap)
            self.assertEqual(len(tree),64)
            self.assertEqual(os.stat(snap/'a.txt').st_mode & 0o222,0)
            self.assertEqual(os.stat(snap).st_mode & 0o222,0)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); repo=root/'repo'; snap=root/'snap'; repo.mkdir(); snap.mkdir(); init_commit(repo)
            outside=root/'outside'; outside.write_text('x'); os.symlink(outside,repo/'link')
            with self.assertRaises(runner.RunnerError): runner.snapshot_repository(repo,snap)

    def test_snapshot_excludes_ignored_secret_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); repo=root/'repo'; snap=root/'snap'; repo.mkdir(); snap.mkdir(); init_commit(repo)
            (repo/'.gitignore').write_text('.env\n.cache/\n')
            (repo/'tracked.txt').write_text('safe')
            subprocess.run(['/usr/bin/git','add','.gitignore','tracked.txt'],cwd=repo,check=True)
            subprocess.run(['/usr/bin/git','commit','-q','-m','tracked inputs'],cwd=repo,check=True)
            (repo/'.env').write_text('AZPR_APPROVAL_PRIVATE_KEY=secret')
            (repo/'.cache').mkdir(); (repo/'.cache'/'token').write_text('secret')
            with self.assertRaisesRegex(runner.RunnerError,"ignored worktree artifacts are forbidden"):
                runner.snapshot_repository(repo,snap)
            self.assertFalse((snap/'.env').exists())
            self.assertFalse((snap/'.cache').exists())

    def test_snapshot_uses_immutable_tree_when_worktree_changes_after_indexing(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); repo=root/'repo'; snap=root/'snap'; repo.mkdir(); snap.mkdir(); init_commit(repo)
            (repo/'tracked.txt').write_text('reviewed')
            original=runner._read_relative_regular
            triggered={'done':False}
            def wrapped(root_fd, relative, **kwargs):
                result=original(root_fd,relative,**kwargs)
                if relative=='tracked.txt' and not triggered['done']:
                    triggered['done']=True
                    (repo/'tracked.txt').write_text('SECRET_TOKEN=late-swap')
                return result
            from unittest import mock
            with mock.patch.object(runner,'_read_relative_regular',side_effect=wrapped):
                with self.assertRaises(runner.RunnerError): runner.snapshot_repository(repo,snap)

    def test_process_output_is_bounded_and_killed(self):
        import sys
        with self.assertRaises(runner.RunnerError):
            runner.run_group([sys.executable,'-c','import sys; sys.stdout.write("x"*200000); sys.stdout.flush()'],30,output_byte_limit=1024)

    def test_container_command_has_required_isolation(self):
        import argparse
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); args=argparse.Namespace(engine='docker',pids_limit=64,cpus='1',memory='1g',file_size_limit=1024,tmpfs_size='64m',image='image@sha256:'+'a'*64)
            argv=runner.build_container_command(args,root/'snapshot',root/'evidence',['python3','-V'])
            joined=' '.join(argv)
            for token in ('--network=none','--ipc=none','--read-only','--cap-drop=ALL','no-new-privileges','readonly'):
                self.assertIn(token,joined)

if __name__=='__main__': unittest.main(verbosity=2)
