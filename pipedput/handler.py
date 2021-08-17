import functools
import logging
import os
import tempfile
from typing import Iterable, Iterator, Union

try:
    from uwsgidecorators import mulefunc
except ImportError:

    def mulefunc(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper


from pipedput.typing import DeploymentStateLike, GitLabPipelineEvent, HookLike
from pipedput.utils import (
    download_file,
    get_api_base_url_from_event,
    render_template,
    send_mail,
    unzip,
)

logger = logging.getLogger(__name__)


def _get_artifact_urls(event: GitLabPipelineEvent) -> Iterator[str]:
    """
    generator that yields artifact urls from a gitlab pipeline event

    url format:
        https://example.com/api/v4/projects/<project_id>/jobs/<job_id>/artifacts
    """
    base_url = get_api_base_url_from_event(event)
    project_id = event["project"]["id"]

    for build in event["builds"]:
        if build["artifacts_file"]["filename"] is not None:
            job_id = build["id"]
            yield f"{base_url}/projects/{project_id}/jobs/{job_id}/artifacts"


def _send_report_mail(event: GitLabPipelineEvent, content: str, **kwargs):
    project_name = event["project"]["path_with_namespace"]
    recipients = {event["user"]["email"]}
    try:
        recipients.add(event["commit"]["author"]["email"])
    except KeyError:
        pass
    send_mail(
        subject=f"[pipedput] {project_name} deployment",
        recipients=list(recipients),
        html=content,
        **kwargs,
    )


def _handle_error():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(project: Project, event: GitLabPipelineEvent):
            try:
                func(project, event)
            except Exception as exc:
                logger.error("Intercepted unexpected error %s.", str(exc), exc_info=exc)
                _send_report_mail(
                    event,
                    render_template("mails/error.html", event=event, exc=exc),
                )

        return wrapper

    return decorator


def _handle_deployment_report():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(project: Project, event: GitLabPipelineEvent):
            notify = False
            deployments = []
            for deployment in func(project, event):  # type: DeploymentStateLike
                logger.info(
                    "Deployment to %s completed %s.",
                    deployment.target_name,
                    "with success" if deployment.was_successful else "with failures",
                )
                notify |= deployment.notify
                deployments.append(deployment)
            if notify:
                _send_report_mail(
                    event,
                    render_template(
                        "mails/deployment.html", event=event, deployments=deployments
                    ),
                )

        return wrapper

    return decorator


class Project:
    """
    Project configuration.

    Project instances that have been assigned to the PROJECTS config variable
    can be used to publish artifacts via the '/api/projects/<key>/publish' API endpoint.
    """

    class DoesNotExist(Exception):
        pass

    def __init__(
        self,
        key: str,
        hooks: Union[HookLike, Iterable[HookLike]] = None,
        pipeline_secret: str = None,
        artifact_download_token: str = None,
    ) -> None:
        """
        :param key: the unique project key
        :param hooks:
            One or more hooks that should be executed for pipeline events
            of this project.
        :param pipeline_secret:
            Refers to the 'Secret Token' field that can and SHOULD be defined
            for each web-hook and is used to check if the pipeline event
            originates from your GitLab.
        :param artifact_download_token:
            A GitLab API token with `api` scope in case you want pipedput to act
            on pipeline events for a private project.
        """
        self.key = key
        self.pipeline_secret = pipeline_secret
        self.artifact_download_token = artifact_download_token
        if hooks is None:
            self.hooks = []
        elif isinstance(hooks, Iterable):
            self.hooks = list(hooks)
        else:
            self.hooks = [hooks]

    def add_hook(self, hook: HookLike):
        self.hooks.append(hook)
        return self


def _process_artifact(
    project: Project, url: str, event: GitLabPipelineEvent
) -> Iterator[DeploymentStateLike]:
    with tempfile.TemporaryDirectory() as run_dir:
        artifact_file = os.path.join(run_dir, "artifacts.zip")
        artifact_dir = os.path.join(run_dir, "data")
        logger.info("Downloading artifact archive from '{}'.".format(url))
        download_file(url, artifact_file, project.artifact_download_token)
        unzip(artifact_file, artifact_dir)
        for hook in project.hooks:
            yield from hook(event, artifact_dir)


@mulefunc
@_handle_error()
@_handle_deployment_report()
def process_project_pipeline(project: Project, event: GitLabPipelineEvent):
    if any(hook.should_execute_for(event) for hook in project.hooks):
        for artifact_url in _get_artifact_urls(event):
            yield from _process_artifact(project, artifact_url, event)
