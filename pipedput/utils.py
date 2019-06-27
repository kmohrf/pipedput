from flask import current_app
import glob
import logging  # noqa: F401
import os.path
import shutil
import subprocess
import tempfile
from typing import Any, Iterable, Iterator, Mapping
import urllib.request
from urllib.parse import urlparse
from werkzeug.local import LocalProxy
import zipfile

logger = LocalProxy(lambda: current_app.logger)  # type: logging.Logger


def invoke_all(iterable: Iterable, method: str = None, *args, **kwargs) -> Iterator:
    for item in iterable:
        _callable = item if method is None else getattr(item, method)
        yield _callable(*args, **kwargs)


def flatten(nested_list: Iterable[Iterable[Any]]):
    return [item for sublist in nested_list for item in sublist]


def pick(mapping: Mapping, *keys):
    return {
        key: value for key, value in mapping.items()
        if key in keys
    }


def download_file(url: str, destination: str) -> None:
    with urllib.request.urlopen(url) as response, open(destination, mode='wb') as output:
        shutil.copyfileobj(response, output)


def unzip(file: str, destination: str) -> None:
    zip_file = zipfile.ZipFile(file)
    zip_file.extractall(destination)
    zip_file.close()


def find_changes(directory: str) -> Iterator[str]:
    yield from glob.iglob(os.path.join(directory, '**/*.changes'), recursive=True)


def dput(change_file, config_file) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(['dput', '-u', '-c', config_file, change_file], check=True)
    except subprocess.CalledProcessError as exc:
        logger.error('could not upload changes with dput', exc_info=exc,
                     extra=dict(change_file=change_file, config=config_file,
                                stderr=exc.stderr))
        raise


def get_artifact_urls(event) -> Iterator[str]:
    """
    generator that yields artifact urls from a gitlab pipeline event

    url format:
        https://example.com/api/v4/projects/<project_id>/jobs/<job_id>/artifacts
    """
    base_url = urlparse(event['project']['web_url'])
    args = {
        'project_id': event['project']['id'],
        'origin': '{}://{}'.format(base_url.scheme, base_url.netloc)
    }

    for build in event['builds']:
        if build['artifacts_file']['filename'] is not None:
            job_id = build['id']
            yield '{origin}/api/v4/projects/{project_id}/jobs/{job_id}/artifacts'\
                .format(job_id=job_id, **args)


def process_artifact(url, dput_config_file) -> Iterator[subprocess.CompletedProcess]:
    with tempfile.TemporaryDirectory() as run_dir:
        artifact_file = os.path.join(run_dir, 'artifacts.zip')
        artifact_dir = os.path.join(run_dir, 'data')
        logger.info('downloading artifact archive from {}'.format(url))
        download_file(url, artifact_file)
        unzip(artifact_file, artifact_dir)
        for change in find_changes(artifact_dir):
            logger.info('uploading changes from {}'.format(change))
            change_file = os.path.basename(change)
            change_name, _ = os.path.splitext(change_file)
            try:
                process = dput(change, dput_config_file)
                logger.info('finished upload process for {}'.format(change), extra=process.stdout)
                yield change_name, True
            except subprocess.CalledProcessError:
                yield change_name, False
