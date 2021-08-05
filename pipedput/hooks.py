import dataclasses
import glob
import logging
import os
import re
import subprocess
import tarfile
import tempfile
from typing import Any, Iterator, Mapping, Optional, Sequence
from urllib.parse import urlsplit

from pipedput.typing import Constraint, DeploymentStateLike, GitLabPipelineEvent

logger = logging.getLogger(__name__)


@dataclasses.dataclass()
class DeploymentState:
    target_name: str
    was_successful: bool
    notify: bool
    asset: Optional[str] = None
    exc: Optional[Exception] = None
    error: Optional[str] = None


class Hook:
    DEFAULT_NAME: Optional[str] = None
    DEFAULT_NOTIFY: bool = True

    def __init__(
        self,
        should_deploy: Constraint = None,
        name: Optional[str] = None,
        notify_on_success: bool = DEFAULT_NOTIFY,
    ):
        self._should_deploy = should_deploy
        self._notify_on_success = notify_on_success
        if name is not None:
            self.name = name
        elif self.DEFAULT_NAME is not None:
            self.name = self.DEFAULT_NAME
        else:
            self.name = self.__class__.__name__

    def _error(self, **kwargs) -> DeploymentState:
        notify = kwargs.pop("notify", True)
        return DeploymentState(self.name, False, notify=notify, **kwargs)

    def _success(self, **kwargs) -> DeploymentState:
        notify = kwargs.pop("notify", self._notify_on_success)
        return DeploymentState(self.name, True, notify=notify, **kwargs)

    def should_execute_for(self, event: GitLabPipelineEvent) -> bool:
        if self._should_deploy is not None:
            return self._should_deploy(event)
        else:
            return True

    def _execute(
        self, event: GitLabPipelineEvent, artifacts_directory: str
    ) -> Iterator[DeploymentStateLike]:
        raise NotImplementedError()

    def __call__(
        self, event: GitLabPipelineEvent, artifacts_directory: str
    ) -> Iterator[DeploymentStateLike]:
        if self.should_execute_for(event):
            try:
                yield from self._execute(event, artifacts_directory)
            except Exception as exc:
                yield self._error(exc=exc)


class GetVersionMixin:
    def __init__(self, clone_token: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._clone_token = clone_token

    def _get_clone_url(self, event: GitLabPipelineEvent):
        """ """
        if self._clone_token is None:
            raise ValueError(
                "clone_token must be defined if you use the GetVersionMixin."
            )
        parsed_url = urlsplit(event["project"]["git_http_url"])
        url = f"{parsed_url.scheme}://PRIVATE-TOKEN:{self._clone_token}@{parsed_url.hostname}"
        if parsed_url.port:
            url += ":" + str(parsed_url.port)
        url += parsed_url.path
        if parsed_url.query:
            url += "?" + parsed_url.query
        return url

    def _get_version(self, event: GitLabPipelineEvent):
        """Retrieves a human readable version name based on git-describe
        for the commit that triggered the pipeline"""
        url = self._get_clone_url(event)
        with tempfile.TemporaryDirectory() as tmp_dir:
            subprocess.run(
                ["git", "clone", "--bare", url, tmp_dir],
                stderr=subprocess.PIPE,
            )
            describe_output = subprocess.check_output(
                ["git", "describe", "--always", "--tags", event["commit"]["id"]],
                cwd=tmp_dir,
            )
            return describe_output.decode().strip()


class GenericGlobHook(Hook):
    GLOB_PATTERN = None

    def __init__(self, glob_pattern: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        if glob_pattern is not None:
            self._glob_pattern = glob_pattern
        elif self.GLOB_PATTERN is not None:
            self._glob_pattern = self.GLOB_PATTERN
        else:
            raise ValueError(f"A glob pattern must be defined for {self.name}.")

    def _glob(self, path):
        return glob.iglob(path, recursive=True)

    def _get_context(
        self, event: GitLabPipelineEvent, artifacts_directory: str
    ) -> Mapping[str, Any]:
        return {}

    def _handle_no_match(self, event: GitLabPipelineEvent):
        pass

    def _execute(
        self, event: GitLabPipelineEvent, artifacts_directory: str
    ) -> Iterator[DeploymentStateLike]:
        ctx = self._get_context(event, artifacts_directory)
        had_match = False
        for filepath in self._glob(
            os.path.join(artifacts_directory, self._glob_pattern)
        ):
            had_match = True
            filename = os.path.basename(filepath)
            yield from self._handle_artifact(event, filepath, filename, **ctx)
        else:
            if not had_match:
                self._handle_no_match(event)

    def _handle_artifact(
        self,
        event: GitLabPipelineEvent,
        artifact_path: str,
        artifact_name: str,
        **kwargs,
    ) -> Iterator[DeploymentStateLike]:
        raise NotImplementedError()


class PublishToPythonRepository(GenericGlobHook):
    DEFAULT_NAME = "python repository"
    GLOB_PATTERN = "**/*.tar.gz"
    DISTRIBUTABLE_PATTERN = re.compile(r"\.egg-info$")
    TWINE_ARGS = []

    def __init__(
        self,
        pypirc_path: Optional[str] = None,
        repository: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._pypirc_path = pypirc_path
        self._repository = repository

    def _is_python_distributable(self, filepath):
        with tarfile.open(filepath) as tar:
            for member in tar.getmembers():
                if self.DISTRIBUTABLE_PATTERN.search(member.name):
                    return True
        return False

    def _twine(
        self, dist_path: str, twine_args: Optional[Sequence[str]] = None
    ) -> subprocess.CompletedProcess:
        args = list(twine_args) if twine_args is not None else []
        if self.TWINE_ARGS:
            args.extend(self.TWINE_ARGS)
        if self._pypirc_path is not None:
            args.extend(["--config-file", self._pypirc_path])
        if self._repository is not None:
            if re.match(r"^https?://", self._repository):
                args.extend(["--repository-url", self._repository])
            else:
                args.extend(["--repository", self._repository])
        cmd = ["twine", "upload", *args, dist_path]

        try:
            return subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as exc:
            logger.error(
                "Could not upload python distributable with twine.",
                exc_info=exc,
                extra=dict(
                    twine_cmd=cmd,
                    change_file=os.path.basename(dist_path),
                    config=self._pypirc_path,
                    twine_output=exc.stdout.decode(),
                ),
            )
            raise

    def _handle_no_match(self, event: GitLabPipelineEvent):
        logger.info(
            "Found no python distributables in artifacts of %s pipeline %s.",
            event["project"]["path_with_namespace"],
            event["object_attributes"]["id"],
        )

    def _handle_artifact(
        self,
        event: GitLabPipelineEvent,
        artifact_path: str,
        artifact_name: str,
        **kwargs,
    ) -> Iterator[DeploymentStateLike]:
        twine_args = kwargs.pop("twine_args", [])
        if self._is_python_distributable(artifact_path):
            logger.info(
                "Uploading python distributable %s for pipeline %s.",
                artifact_name,
                event["object_attributes"]["id"],
            )
            try:
                process = self._twine(artifact_path, twine_args)
            except subprocess.CalledProcessError as exc:
                logger.error(
                    "Unable to upload python distributable %s for pipeline %s.",
                    artifact_name,
                    event["object_attributes"]["id"],
                )
                yield self._error(asset=artifact_name, exc=exc)
            else:
                logger.info(
                    "Finished upload for python distributable %s for pipeline %s.",
                    artifact_name,
                    event["object_attributes"]["id"],
                    extra=dict(stdout=process.stdout),
                )
                yield self._success(asset=artifact_name)


class PublishToDebRepository(GenericGlobHook):
    DEFAULT_NAME = "deb repository"
    GLOB_PATTERN = "**/*.changes"
    DPUT_ARGS = ["--unchecked"]

    def __init__(self, dput_config_path: str, **kwargs):
        self._dput_config_path = dput_config_path
        super().__init__(**kwargs)

    def _dput(
        self, change_path: str, dput_args: Optional[Sequence[str]] = None
    ) -> subprocess.CompletedProcess:
        args = list(dput_args) if dput_args is not None else []
        if self.DPUT_ARGS:
            args.extend(self.DPUT_ARGS)
        cmd = ["dput", "--config", self._dput_config_path, *args, change_path]
        try:
            return subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as exc:
            logger.error(
                "Could not upload deb changes with dput.",
                exc_info=exc,
                extra=dict(
                    change_file=change_path,
                    config=self._dput_config_path,
                    dput_output=exc.stdout.decode(),
                ),
            )
            raise

    def _handle_no_match(self, event: GitLabPipelineEvent):
        logger.info(
            "Found no deb changes in artifacts of %s pipeline %s.",
            event["project"]["path_with_namespace"],
            event["object_attributes"]["id"],
        )

    def _handle_artifact(
        self,
        event: GitLabPipelineEvent,
        artifact_path: str,
        artifact_name: str,
        **kwargs,
    ) -> Iterator[DeploymentStateLike]:
        dput_args = kwargs.pop("dput_args", [])
        logger.info(
            "Uploading deb changes from %s for pipeline %s.",
            artifact_name,
            event["object_attributes"]["id"],
        )
        try:
            process = self._dput(artifact_path, dput_args)
        except subprocess.CalledProcessError as exc:
            logger.error(
                "Unable to upload change %s to deb repository for pipeline %s.",
                artifact_name,
                event["object_attributes"]["id"],
            )
            yield self._error(asset=artifact_name, exc=exc, error=exc.stderr)
        else:
            logger.info(
                "Finished upload for deb change %s for pipeline %s.",
                artifact_name,
                event["object_attributes"]["id"],
                extra=dict(stdout=process.stdout),
            )
            yield self._success(asset=artifact_name)
