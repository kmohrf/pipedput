import logging

# There is a lot more to discover, where this is coming from!
from pipedput.conf import (
    IsTag,
    OnDefaultBranch,
    Project,
    PublishToDebRepository,
    PublishToPythonRepository,
    WasSuccessful,
)

from pipedput_extensions.example_hooks import BackupJPEGs, IsUser

# Configure logging for your needs.
# See: https://docs.python.org/3/howto/logging.html
logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)

# Mail settings are important for deployment reports!
# See: https://pythonhosted.org/Flask-Mail/#configuring-flask-mail
MAIL_SERVER = "mail.example.org"
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = "pipedput@mail.example.org"
MAIL_PASSWORD = "abc123"
MAIL_DEFAULT_SENDER = "pipedput@mail.example.org"

# You can define any type of variables like you would
# in any other python file!
pipeline_token = "my_secret_pipeline_token"
gitlab_api_token = "a-gitlab-token"
# files must be readable by the _pipedput user
dput_cfg = "/etc/pipedput/my-vendor.dput.cf"
pipy_cfg = "/etc/pipedput/my-vendor.pypirc"

# The bitwise operators &, | and ~ (AND, OR, NOT) can be used
# to build complex constraints that define, if your hook
# should be executed!
on_default_branch = OnDefaultBranch(gitlab_api_token)
on_default_branch_and_successful = on_default_branch & WasSuccessful()
is_release = on_default_branch_and_successful & IsTag()

PROJECTS = [
    Project(
        # This key must be unique!
        "my-private-project",
        PublishToDebRepository(dput_cfg, should_deploy=is_release),
        # It’s good to protect your pipeline handlers with a secret!
        # Fill in a 'Secret Token' in the GitLab Web-Hook settings and
        # set it to the pipeline_secret option.
        pipeline_secret=pipeline_token,
        # Artifacts of non-public projects need a download token.
        # You can create a personal or project access token and set it here.
        artifact_download_token=gitlab_api_token,
    ),
    Project(
        "my-project",
        # You can define multiple hooks for the same project by passing a list
        # instead of a single hook!
        [
            PublishToDebRepository(dput_cfg, should_deploy=is_release),
            PublishToPythonRepository(
                pipy_cfg, should_deploy=on_default_branch_and_successful
            ),
        ],
    ),
    Project(
        "mockups",
        # Use custom hooks and constraints!
        BackupJPEGs(should_deploy=IsUser("our_cool_designer")),
    ),
]
