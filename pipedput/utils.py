import shutil
import socket
import urllib.error
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile

from flask import current_app
from flask_mail import Message
from jinja2 import Environment, PackageLoader

from pipedput.typing import GitLabPipelineEvent


_jinja_env = Environment(
    loader=PackageLoader("pipedput"),
)


def download_file(url: str, destination: str, token: str = None) -> None:
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


def send_mail(**kwargs):
    from pipedput.app import app, mail

    with app.app_context():
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
