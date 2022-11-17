from contextlib import contextmanager
import os
from os.path import join
import tarfile
import tempfile
from typing import Iterator, Optional
import unittest
from unittest.mock import MagicMock, patch

from pipedput.hooks import (
    GetVersionMixin,
    Hook,
    PublishToDebRepository,
    PublishToPythonRepository,
)
from pipedput.typing import DeploymentStateLike, GitLabPipelineEvent
from pipedput.utils import Configuration
from tests.utils import ContainedInOrderMixin, FILES_DIR


class SubprocessRunResult:
    def __init__(self, stdout: Optional[bytes] = None, stderr: Optional[bytes] = None):
        self.stdout = stdout or bytes()
        self.stderr = stderr or bytes()


class GetVersionHook(GetVersionMixin, Hook):
    def _execute(
        self, event: GitLabPipelineEvent, artifacts_directory: str
    ) -> Iterator[DeploymentStateLike]:
        version = self._get_version(event)
        yield self._success(asset=version)


class RepoTestMixin:
    @contextmanager
    def _init_test_repo(self):
        with tempfile.TemporaryDirectory(
            dir=os.environ.get("envtmpdir", None)
        ) as temp_dir:
            with tarfile.open(join(FILES_DIR, "repo.tar.gz")) as tar:
                def is_within_directory(directory, target):
                    
                    abs_directory = os.path.abspath(directory)
                    abs_target = os.path.abspath(target)
                
                    prefix = os.path.commonprefix([abs_directory, abs_target])
                    
                    return prefix == abs_directory
                
                def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                
                    for member in tar.getmembers():
                        member_path = os.path.join(path, member.name)
                        if not is_within_directory(path, member_path):
                            raise Exception("Attempted Path Traversal in Tar File")
                
                    tar.extractall(path, members, numeric_owner=numeric_owner) 
                    
                
                safe_extract(tar, temp_dir)
            yield f"file://{temp_dir}/test-repo"


class GetVersionHookTest(RepoTestMixin, unittest.TestCase):
    def _get_version_for(self, commit_sha) -> DeploymentStateLike:
        hook = GetVersionHook("abc123")
        with self._init_test_repo() as repo_url:
            config = {
                "project": {"git_http_url": repo_url},
                "commit": {"id": commit_sha},
            }
            return list(hook(config, "foo"))[0]

    @patch.dict(os.environ, {"PATH": ""})
    def test_fails_if_git_bin_is_missing(self):
        deployment = self._get_version_for("4aa551d1b8da6fbddd593d5b50c7991b86593b2d")
        self.assertFalse(deployment.was_successful)
        self.assertIsNotNone(deployment.exc)
        self.assertIn("Could not find 'git' binary", str(deployment.exc))

    def test_no_tags_version(self):
        deployment = self._get_version_for("4aa551d1b8da6fbddd593d5b50c7991b86593b2d")
        self.assertTrue(deployment.was_successful)
        self.assertEqual(deployment.asset, "4aa551d")

    def test_tag_version(self):
        deployment = self._get_version_for("de030c0b8ceef848e0efef8f6c25ee60b036b7bc")
        self.assertTrue(deployment.was_successful)
        self.assertEqual(deployment.asset, "v0.1.4")

    def test_post_tag_version(self):
        deployment = self._get_version_for("06ce2aaeb9621563b8ead91a76ee370cf93366f4")
        self.assertTrue(deployment.was_successful)
        self.assertEqual(deployment.asset, "v0.1.4-1-g06ce2aa")


class PublishToPythonRepositoryHookTest(ContainedInOrderMixin, unittest.TestCase):
    SAMPLE_CONFIG = os.path.join(FILES_DIR, "sample.pypirc")

    @patch.dict(os.environ, {"PATH": ""})
    def test_fails_if_twine_bin_is_missing(self):
        hook = PublishToPythonRepository(self.SAMPLE_CONFIG)
        with self.assertRaises(Configuration.ConfigurationError):
            hook._twine("foo.tar.gz")

    @patch("subprocess.run")
    def test_fails_if_config_file_is_missing(self, subprocess_run: MagicMock):
        subprocess_run.return_value = SubprocessRunResult()
        config_file = "does_not_exist.pypirc"
        hook = PublishToPythonRepository(config_file)
        with self.assertRaises(Configuration.ConfigurationError):
            hook._twine("foo.tar.gz")
            subprocess_run.assert_not_called()

    @patch("subprocess.run")
    def test_twine_with_config(self, subprocess_run: MagicMock):
        subprocess_run.return_value = SubprocessRunResult()
        hook = PublishToPythonRepository(self.SAMPLE_CONFIG)
        hook._twine("foo.tar.gz")
        subprocess_run.assert_called_once()
        self.assertInOrder(
            ["--config-file", self.SAMPLE_CONFIG],
            subprocess_run.call_args[0][0],
        )

    @patch("subprocess.run")
    def test_twine_with_repository(self, subprocess_run: MagicMock):
        subprocess_run.return_value = SubprocessRunResult()
        hook = PublishToPythonRepository(repository="foo")
        hook._twine("foo.tar.gz")
        subprocess_run.assert_called_once()
        self.assertInOrder(
            ["--repository", "foo"],
            subprocess_run.call_args[0][0],
        )

    @patch("subprocess.run")
    def test_twine_with_repository_url(self, subprocess_run: MagicMock):
        subprocess_run.return_value = SubprocessRunResult()
        hook = PublishToPythonRepository(repository="https://foo")
        hook._twine("foo.tar.gz")
        subprocess_run.assert_called_once()
        self.assertInOrder(
            ["--repository-url", "https://foo"],
            subprocess_run.call_args[0][0],
        )


class PublishToDebRepositoryHookTest(ContainedInOrderMixin, unittest.TestCase):
    SAMPLE_CONFIG = os.path.join(FILES_DIR, "sample.dput.cf")

    @patch.dict(os.environ, {"PATH": ""})
    def test_fails_if_dput_bin_is_missing(self):
        hook = PublishToDebRepository(self.SAMPLE_CONFIG)
        with self.assertRaises(Configuration.ConfigurationError):
            hook._dput("foo.tar.gz")

    @patch("subprocess.run")
    def test_fails_if_config_file_is_missing(self, subprocess_run: MagicMock):
        subprocess_run.return_value = SubprocessRunResult()
        config_file = "does_not_exist.dput.cf"
        hook = PublishToDebRepository(config_file)
        with self.assertRaises(Configuration.ConfigurationError):
            hook._dput("foo.deb")
            subprocess_run.assert_not_called()

    @patch("subprocess.run")
    def test_dput_execution(self, subprocess_run: MagicMock):
        subprocess_run.return_value = SubprocessRunResult()
        hook = PublishToDebRepository(self.SAMPLE_CONFIG)
        hook._dput("foo.deb")
        subprocess_run.assert_called_once()
        self.assertInOrder(
            ["dput", "--config", self.SAMPLE_CONFIG],
            subprocess_run.call_args[0][0],
        )
