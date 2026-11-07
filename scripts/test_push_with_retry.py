"""Offline integration tests using isolated local Git repositories."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('push_with_retry.sh').resolve()


class PushTests(unittest.TestCase):
    def git(self, cwd, *args):
        return subprocess.check_output(['git', '-C', str(cwd), *args], stderr=subprocess.DEVNULL, text=True).strip()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.remote = self.root / 'remote.git'
        self.git(self.root, 'init', '--bare', '--initial-branch=main', str(self.remote))
        self.a = self.root / 'a'
        self.b = self.root / 'b'
        self.git(self.root, 'clone', str(self.remote), str(self.a))
        self.configure(self.a)
        self.commit(self.a, 'data.json', 'baseline\n')
        self.git(self.a, 'push', 'origin', 'main')
        self.git(self.root, 'clone', str(self.remote), str(self.b))
        self.configure(self.b)

    def configure(self, repo):
        self.git(repo, 'config', 'user.name', 'Test')
        self.git(repo, 'config', 'user.email', 'test@example.invalid')

    def commit(self, repo, path, content):
        (repo / path).write_text(content)
        self.git(repo, 'add', path)
        self.git(repo, 'commit', '-m', 'test change')

    def publish(self, **env):
        return subprocess.run(['bash', str(SCRIPT)], cwd=self.a,
                              env={**os.environ, 'GITHUB_REF_NAME': 'main', **env},
                              capture_output=True, text=True)

    def test_clean_push(self):
        self.commit(self.a, 'queue.json', 'new candidate\n')
        self.assertEqual(self.publish().returncode, 0)
        self.assertEqual(self.git(self.remote, 'show', 'main:queue.json'), 'new candidate')

    def test_preserves_unrelated_remote_update(self):
        self.commit(self.a, 'queue.json', 'new candidate\n')
        self.commit(self.b, 'manual.json', 'human edit\n')
        self.git(self.b, 'push', 'origin', 'main')
        self.assertEqual(self.publish().returncode, 0)
        self.assertEqual(self.git(self.remote, 'show', 'main:queue.json'), 'new candidate')
        self.assertEqual(self.git(self.remote, 'show', 'main:manual.json'), 'human edit')

    def test_same_line_conflict_fails_without_data_loss(self):
        self.commit(self.a, 'data.json', 'collected\n')
        local_head = self.git(self.a, 'rev-parse', 'HEAD')
        self.commit(self.b, 'data.json', 'reviewed by human\n')
        self.git(self.b, 'push', 'origin', 'main')
        remote_head = self.git(self.remote, 'rev-parse', 'main')
        self.assertNotEqual(self.publish().returncode, 0)
        self.assertEqual(self.git(self.remote, 'rev-parse', 'main'), remote_head)
        self.assertEqual(self.git(self.a, 'rev-parse', 'HEAD'), local_head)
        self.assertEqual((self.a / 'data.json').read_text(), 'collected\n')
        self.assertFalse((self.a / '.git/rebase-merge').exists())

    def test_race_after_fetch_is_retried(self):
        self.commit(self.a, 'queue.json', 'new candidate\n')
        self.commit(self.b, 'manual.json', 'late human edit\n')
        hook = self.a / '.git/hooks/pre-push'
        hook.write_text('#!/bin/sh\nrm -- "$0"\ngit -C "' + str(self.b) + '" push origin main\n')
        hook.chmod(0o755)
        self.assertEqual(self.publish().returncode, 0)
        self.assertEqual(self.git(self.remote, 'show', 'main:manual.json'), 'late human edit')
        self.assertEqual(self.git(self.remote, 'show', 'main:queue.json'), 'new candidate')

    def test_permanent_push_failure_stops_after_five_attempts(self):
        self.commit(self.a, 'queue.json', 'new candidate\n')
        head = self.git(self.remote, 'rev-parse', 'main')
        counter = self.root / 'count'
        hook = self.a / '.git/hooks/pre-push'
        hook.write_text('#!/bin/sh\necho attempt >> "' + str(counter) + '"\nexit 1\n')
        hook.chmod(0o755)
        self.assertNotEqual(self.publish().returncode, 0)
        self.assertEqual(len(counter.read_text().splitlines()), 5)
        self.assertEqual(self.git(self.remote, 'rev-parse', 'main'), head)


if __name__ == '__main__':
    unittest.main()
