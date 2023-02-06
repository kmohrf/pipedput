import logging
from logging.handlers import MemoryHandler

from pipedput.conf import (
    Contact,
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

api_token = "abc123"
on_default_branch = OnDefaultBranch(api_token)
on_default_branch_and_successful = on_default_branch and WasSuccessful()
is_release = on_default_branch_and_successful and IsTag()
qualifies_artifact = on_default_branch_and_successful or WasManuallyTriggered()


def to_deb_repo():
    return PublishToDebRepository("dummy.cfg", should_deploy=is_release)


def to_pypi_repo(**kwargs):
    return PublishToPythonRepository("dummy.cfg", should_deploy=is_release, **kwargs)


class FailHook(Hook):
    def __call__(self, *args, **kwargs):
        raise RuntimeError("nope")


TESTING = True
MAIL_SERVER = "localhost"
MAIL_PORT = 25
MAIL_DEFAULT_SENDER = "noreply@localhost"
DEFAULT_MAIL_RECIPIENTS = ["tester@localhost"]
DEPLOYMENT_DOCUMENTATION_URL = (
    "https://our-internal-deployment-documentation.example.org"
)
PROJECTS = [
    Project("deb", to_deb_repo()),
    Project("pypi", to_pypi_repo()),
    Project("pypi-to-gitlab", to_pypi_repo(publish_to_gitlab=True)),
    Project("deb-and-pypi", [to_deb_repo(), to_pypi_repo()]),
    Project("auth", None, "cde456"),
    Project("with-gitlab-token", to_deb_repo(), artifact_download_token=api_token),
    Project("fail-badly", FailHook()),
    Project(
        "deb-with-maintainers",
        to_deb_repo(),
        maintainers=[
            Contact("Ingo", "ingo@gitlab.localhost"),
            Contact("Commit Author", "user@gitlab.localhost"),
        ],
    ),
]
