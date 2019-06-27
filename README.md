# pipedput

pipedput is a small flask-based web service that acts as a web-hook receiver for GitLab pipeline events. It scans the event payload for artifacts, downloads and extracts them and pushes all `*.changes` files to a Debian-compatible deb-repository with the help of [dput](https://packages.debian.org/source/sid/dput).

## Dependencies

pipedput only needs flask to run and is built against the current stable version from Debian Stretch, though it should work just fine with more recent versions.

## Server Configuration

### Application

When pipedput is started it expects the environment variable `PIPEDPUT_CONFIG_FILE` to be set to the **absolute path** of the config file. This config file is executed as python code and must set the `PROJECT_CONFIGS` variable. See the following example:

```python
import os.path
from pipedput.config import ProjectConfig
from pipedput.constraints import RequireTag, RequireSuccess

BASE_PATH = os.path.realpath(os.path.dirname(__file__))

myproject = ProjectConfig('myproject', os.path.join(BASE_PATH, 'myproject.dput.cf'),
                          token='my-secret-token')
myproject.add_constraint(
    RequireTag(),
    RequireSuccess())

PROJECT_CONFIGS = [
    myproject
]
```

Each `ProjectConfig` must be initialized with the project name and a dput configuration, that is used to push the generated deb packages to the deb repository. Optional parameters include:

 `token` which refers to the *Secret Token* field that can **and SHOULD** be defined for each web-hook and is used to check if the pipeline event originates from your GitLab and

 `artifact_token` referring to an access token with `api` scope in case you want pipedput to act on pipeline events for a private project.

### Web Server

uWSGI is recommended for running pipedput in production. See the example configurations for [uWSGI](./debian/uwsgi.ini) and [NGINX](./debian/nginx.conf).

## Web-Hook Configuration

Once installed on a server you can add the following URL to your GitLab Web-Hook page:

```
https://example.com/api/projects/<project>/publish
```

where `<project>` refers to the first argument you’ve passed to `ProjectConfig` (in the example configuration from above this is `myproject`).

## Future

This project is considered feature-complete for as long as GitLab doesn’t change the content of the pipeline event payload. Low update-frequency is not an indication of lack of maintenance :).

Feel free to submit issues and pull requests in case you’ll find something that is missing though!

## License

pipedput is released under the terms of the GNU Affero General Public License v3 or later.
    
