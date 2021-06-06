import os
from typing import Optional

from flask import Flask, request
from flask_mail import Mail

from pipedput import __version__
from pipedput.handler import process_project_pipeline, Project
from pipedput.typing import GitLabPipelineEvent

app = Flask("pipedput")
config_file = os.environ.get("PIPEDPUT_CONFIG_FILE", None)
if config_file is None:
    raise ImportError("please set the PIPEDPUT_CONFIG_FILE environment variable")
if not os.path.isabs(config_file):
    raise ImportError("please provide an absolute path for the config file")
app.config.from_pyfile(os.path.realpath(config_file))
mail = Mail(app)

SENTRY_DSN = app.config.get("SENTRY_DSN", None)
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FlaskIntegration()],
        send_default_pii=True,
        release=f"pipedput@v{__version__}",
    )


def get_project_by_key(key: str) -> Project:
    for project in app.config["PROJECTS"]:  # type: Project
        if project.key == key:
            return project
    raise Project.DoesNotExist()


def is_allowed(project: Project, token: Optional[str]) -> bool:
    return project.pipeline_secret is None or project.pipeline_secret == token


@app.route("/api/projects/<project_key>/publish", methods=["POST"])
def handle_pipeline_event(project_key: str):
    event: GitLabPipelineEvent = request.json

    try:
        project = get_project_by_key(project_key)
    except Project.DoesNotExist:
        return f"No project identified by {project_key} is defined.", 404

    if not is_allowed(project, request.headers.get("X-Gitlab-Token", None)):
        return f"You’re not allowed to publish {project_key}.", 403

    try:
        if event.get("object_kind", None) != "pipeline":
            raise ValueError()
    except (AttributeError, ValueError):
        return "Only pipeline events will be processed.", 400

    app.logger.info(
        "Accepted request for pipeline %s for project %s finished at %s with ref %s.",
        event["object_attributes"]["id"],
        event["project"]["path_with_namespace"],
        event["object_attributes"]["finished_at"],
        event["object_attributes"]["ref"],
    )
    process_project_pipeline(project, event)
    return "Request accepted.", 200


if __name__ == "__main__":
    app.run()
