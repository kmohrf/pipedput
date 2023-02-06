import logging
import os
import shutil
import socket
from typing import Optional
import urllib.error
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile

from flask import current_app
from flask_mail import Message
import html2text
from jinja2 import Environment, PackageLoader

from pipedput.typing import GitLabPipelineEvent


_logger = logging.getLogger(__name__)
_jinja_env = Environment(
    loader=PackageLoader("pipedput"),
)


def get_url_hostname(url: str):
    return urlparse(url).hostname


def download_file(url: str, destination: str, token: Optional[str] = None) -> None:
    request = Request(url)
    if token is not None:
        request.add_header("PRIVATE-TOKEN", token)
    try:
        with urlopen(request) as response, open(destination, mode="wb") as output:
            shutil.copyfileobj(response, output)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError(
                "Pipeline artifact is reported as not found. "
                "Did you forget to specify an artifact download "
                "token in the configuration?"
            ) from exc
        raise


def unzip(file: str, destination: str) -> None:
    zip_file = zipfile.ZipFile(file)
    zip_file.extractall(destination)
    zip_file.close()


def get_api_base_url_from_event(event: GitLabPipelineEvent) -> str:
    base_url = urlparse(event["project"]["web_url"])
    return f"{base_url.scheme}://{base_url.netloc}/api/v4"


def html_to_markdown(html: str, width: int = 72) -> str:
    return html2text.html2text(html, bodywidth=width)


def send_mail(**kwargs):
    from pipedput.app import app, mail

    with app.app_context():
        if "html" in kwargs and "body" not in kwargs:
            kwargs["body"] = html_to_markdown(kwargs["html"])

        message = Message(**kwargs)
        default_recipients = current_app.config.get("DEFAULT_MAIL_RECIPIENTS", [])
        if default_recipients:
            message.bcc.extend(default_recipients)
        mail.send(message)


def render_template(template_name: str, **context):
    template = _jinja_env.get_template(template_name)
    hostname = socket.gethostname()
    return template.render(
        hostname=hostname,
        **context,
    )


def create_template_renderer(template_name: str, **context_defaults):
    def _render_template(**context):
        context_defaults.update(context)
        return render_template(template_name, **context_defaults)

    return _render_template


class Configuration:
    class ConfigurationError(Exception):
        pass

    @classmethod
    def _check(cls, condition: bool, message: str, warn_only: bool):
        if condition:
            if warn_only:
                _logger.warning(message)
            else:
                raise cls.ConfigurationError(message)

    @classmethod
    def assert_false(cls, condition: bool, message: str, warn_only: bool = False):
        cls._check(condition, message, warn_only)

    @classmethod
    def check_bin_exists(cls, bin_name: str, warn_only: bool = False):
        cls._check(
            shutil.which(bin_name) is None,
            f"Could not find '{bin_name}' binary on PATH, but it is required. "
            f"Did you forget to install it on the system?",
            warn_only,
        )

    @classmethod
    def check_file_exists(cls, file_path: str, warn_only: bool = False):
        cls._check(
            not os.path.exists(file_path),
            f"The file '{file_path}' was specified in the configuration but "
            f"does not exist.",
            warn_only,
        )


_jinja_env.filters["url_hostname"] = get_url_hostname
