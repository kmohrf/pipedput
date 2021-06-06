from contextlib import contextmanager
import functools
import glob
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os
from os.path import dirname, join
import re
import subprocess
import threading
from unittest.mock import MagicMock, patch

import lxml.etree

from pipedput.typing import GitLabPipelineEvent

BASE_DIR = dirname(__file__)
FILES_DIR = join(BASE_DIR, "files")
BIN_DIR = join(BASE_DIR, "bin")
# We could probably make this configurable but this would
# mean that we need to generate events with the proper
# urls that contain the configured port and that is some work
# that no one wants to do right now so it’s hardcoded for now :).
HTTP_TEST_SERVER_PORT = 31312

logger = logging.getLogger(__name__)


def css_query_select(content, selector):
    el = lxml.etree.fromstring(content, parser=lxml.etree.HTMLParser())
    selected = el.cssselect(selector)
    if len(selected) > 0:
        return lxml.etree.tostring(selected[0], pretty_print=True).decode()
    else:
        return None


class TestFileMock(MagicMock):
    def __init__(self, test_filename, *args, **kwargs):
        @contextmanager
        def side_effect(*args, **kwargs):
            with open(join(FILES_DIR, test_filename), "rb") as test_file:
                yield test_file

        super().__init__(*args, side_effect=side_effect, **kwargs)


def get_bin_mock(bin_name, fail):
    def callback(*args, **kwargs):
        str_args = [arg for arg in args if isinstance(arg, str)]
        return subprocess.run(
            [join(BIN_DIR, bin_name), "fail" if fail else "succeed", *str_args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    return callback


def create_bin_patcher(target, bin_name):
    def bin_patcher(fail=False, inject_mock_as=None, **patch_kwargs):
        mock = MagicMock(name=bin_name, side_effect=get_bin_mock(bin_name, fail))
        patch_func = patch(target, mock, **patch_kwargs)
        if inject_mock_as:

            def decorator(func):
                @patch_func
                @functools.wraps(func)
                def wrapper(*args, **kwargs):
                    kwargs[inject_mock_as] = mock
                    return func(*args, **kwargs)

                return wrapper

            return decorator
        else:
            return patch_func

    return bin_patcher


class MockGitLabServer(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    close_connection = True

    ARTIFACTS_PATTERN = re.compile(r"jobs/(?P<build_id>[0-9]+)/artifacts$")
    COMMIT_REFS_PATTERN = re.compile(r"commits/(?P<commit_sha>[a-zA-Z0-9]+)/refs$")

    @contextmanager
    def _find_artifact(self, build_id):
        for filepath in glob.glob(join(FILES_DIR, "events", "*.json")):
            with open(filepath) as file:
                content: GitLabPipelineEvent = json.load(file)
            for build in content["builds"]:
                if build["id"] == build_id:
                    artifact_name = build["artifacts_file"]["filename"]
                    artifact_filepath = join(FILES_DIR, "artifacts", artifact_name)
                    with open(artifact_filepath, "rb") as artifact:
                        try:
                            yield artifact
                        finally:
                            return
        raise FileNotFoundError("No artifact found for build id")

    def _size(self, named_io):
        return str(os.stat(named_io.name).st_size)

    def _handle_artifact(self, match):
        with self._find_artifact(int(match.group("build_id"))) as artifact:
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", self._size(artifact))
            self.end_headers()
            self.wfile.write(artifact.read())

    def _handle_commit_ref(self, match):
        commit_sha = match.group("commit_sha")
        commit_refs_filename = f"{commit_sha}.json"
        commit_refs_path = join(FILES_DIR, "commit-refs", commit_refs_filename)
        with open(commit_refs_path, "rb") as commit_refs:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", self._size(commit_refs))
            self.end_headers()
            self.wfile.write(commit_refs.read())

    def _check_auth(self):
        auth_token = self.headers.get("PRIVATE-TOKEN", None)
        if auth_token is not None:
            if auth_token != "abc124":
                self.send_response(404)
                self.wfile.write("Unauthorized".encode())
                self.end_headers()
                return False
        return True

    def do_GET(self):
        logging.info("Got a GitLab request for '%s'.", self.path)
        if not self._check_auth():
            return

        for pattern, callback in (
            (self.ARTIFACTS_PATTERN, self._handle_artifact),
            (self.COMMIT_REFS_PATTERN, self._handle_commit_ref),
        ):
            match = pattern.search(self.path)
            if match is not None:
                try:
                    callback(match)
                except FileNotFoundError:
                    self.send_response(404)
                    self.wfile.write("Not found".encode())
                    self.end_headers()

    def log_message(self, format, *args):
        pass


def start_gitlab_mock_server(daemonize=True):
    mock_server = HTTPServer(
        ("gitlab.localhost", HTTP_TEST_SERVER_PORT), MockGitLabServer
    )
    mock_server_thread = threading.Thread(target=mock_server.serve_forever)
    mock_server_thread.setDaemon(daemonize)
    mock_server_thread.start()


if __name__ == "__main__":
    start_gitlab_mock_server(False)
