# pipedput

pipedput is a small flask-based web service that acts as a web-hook
receiver for GitLab pipeline events. It scans the event payload for
artifacts, downloads and extracts them and then defers control to
hooks configured by you.

Support for pushing to deb and pypi repositories is built-in.

## Installation

Releases come with deb packages that you can install on your system.
See the [releases page](https://git.hack-hro.de/kmohrf/pipedput/-/releases).

You may install the deb packages with dpkg:

```sh
dpkg -i pipedput python3-pipedput
apt --fix-broken install -t buster-backports
```

A deb repository for your convenience is in the works.

## Application Configuration

Your config file should be placed in `/etc/pipedput/config.py`,
is executed as python code and must set the `PROJECTS` variable.
See the following example:

```python
import logging

# There is a lot more to discover, where this is coming from!
from pipedput.conf import (
    Contact,
    IsTag,
    OnDefaultBranch,
    Project,
    PublishToDebRepository,
    PublishToPythonRepository,
    WasSuccessful,
)

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

# A link to your documentation will be included in outgoing
# mail notifications if you set this option.
DEPLOYMENT_DOCUMENTATION_URL = "https://our-internal-deployment-documentation.example.org"

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
            PublishToPythonRepository(pipy_cfg, should_deploy=on_default_branch_and_successful)
        ],
        # Email notifications for deployments and errors are sent to the user
        # who triggered the pipeline and authored the commit by default. If
        # you add maintainers to your project configuration they will receive
        # these notifications as well.
        maintainers={
            Contact("A maintainer", "maintainer@example.com"),
        },
    ),
]

```

pipedput integrates Flask-Mail for sending deployment reports. See the
[configuration variables](https://pythonhosted.org/Flask-Mail/#configuring-flask-mail)
of Flask-Mail to enable these reports.

## Web-Hook Configuration

Once installed on a server you can add the following URL to your
GitLab Web-Hook page:

```
https://example.com/api/projects/<project_key>/publish
```

where `<project_key>` refers to the first argument you’ve passed to
`Project` (in the example configuration from above this is `my-project`).

## Future

This project is considered feature-complete for as long as GitLab
doesn’t change the content of the pipeline event payload.
Low update-frequency is not an indication of lack of maintenance :).

Feel free to submit issues and pull requests in case you’ll find
something that is missing though!

## License

pipedput is released under the terms of the
*GNU Affero General Public License v3 or later*.
