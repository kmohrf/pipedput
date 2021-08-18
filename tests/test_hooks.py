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
                tar.extractall(temp_dir)
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
    @patch("subprocess.run")
    def test_twine_with_config(self, subprocess_run: MagicMock):
        subprocess_run.return_value = SubprocessRunResult()
        hook = PublishToPythonRepository("foo.pypirc")
        hook._twine("foo.tar.gz")
        subprocess_run.assert_called_once()
        self.assertInOrder(
            ["--config-file", "foo.pypirc"],
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
