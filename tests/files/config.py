import logging
from logging.handlers import MemoryHandler

from pipedput.conf import (
    Hook,
    IsTag,
    OnDefaultBranch,
    Project,
    PublishToDebRepository,
    PublishToPythonRepository,
    WasManuallyTriggered,
    WasSuccessful,
)

logging.basicConfig(
    level=logging.INFO,
    handlers=[MemoryHandler(32 * 1024 * 1024)],
)

gitlab_api_token = "abc123"
on_default_branch = OnDefaultBranch(gitlab_api_token)
on_default_branch_and_successful = on_default_branch and WasSuccessful()
is_release = on_default_branch_and_successful and IsTag()
qualifies_artifact = on_default_branch_and_successful or WasManuallyTriggered()


def project(key, hooks, pipeline_secret=None, gitlab_api_token=None):
    return Project(key, hooks, pipeline_secret, gitlab_api_token)


def to_deb_repo():
    return PublishToDebRepository("dummy.cfg", should_deploy=is_release)


def to_pypi_repo():
    return PublishToPythonRepository("dummy.cfg", should_deploy=is_release)


class FailHook(Hook):
    def __call__(self, *args, **kwargs):
        raise RuntimeError("nope")


TESTING = True
MAIL_SERVER = "localhost"
MAIL_PORT = 25
MAIL_DEFAULT_SENDER = "noreply@localhost"
DEFAULT_MAIL_RECIPIENTS = ["tester@localhost"]
PROJECTS = [
    project("deb", to_deb_repo()),
    project("pypi", to_pypi_repo()),
    project("deb-and-pypi", [to_deb_repo(), to_pypi_repo()]),
    project("auth", None, "cde456"),
    project("with-gitlab-token", to_deb_repo(), gitlab_api_token=gitlab_api_token),
    project("fail-badly", FailHook()),
]
