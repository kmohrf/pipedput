import datetime
import json
import os
from os.path import join
import unittest
from unittest.mock import MagicMock

from tests.utils import (
    create_bin_patcher,
    css_query_select,
    FILES_DIR,
    start_gitlab_mock_server,
)

os.environ.setdefault("PIPEDPUT_CONFIG_FILE", join(FILES_DIR, "config.py"))

from pipedput.app import app, mail  # noqa: E402 I100 I202

patch_twine = create_bin_patcher(
    "pipedput.hooks.PublishToPythonRepository._twine", "twine"
)
patch_dput = create_bin_patcher("pipedput.hooks.PublishToDebRepository._dput", "dput")


class FlaskTest(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.app = app.test_client()
        self.assertEqual(app.testing, True)
        self.assertEqual(app.debug, False)

    def _load_event(self, name):
        with open(join(FILES_DIR, "events", name)) as json_test_file:
            return json.load(json_test_file)


class APISecurityTest(FlaskTest):
    def test_reject_invalid_project_key(self):
        res = self.app.post("/api/projects/__invalid_project_key__/publish", json={})
        self.assertEqual(res.status_code, 404)

    def test_reject_missing_access_token(self):
        res = self.app.post("/api/projects/auth/publish", json={})
        self.assertEqual(res.status_code, 403)

    def test_reject_invalid_access_token(self):
        res = self.app.post(
            "/api/projects/auth/publish",
            headers={"X-Gitlab-Token": "__invalid_token__"},
        )
        self.assertEqual(res.status_code, 403)

    def test_accept_valid_access_token(self):
        res = self.app.post(
            "/api/projects/auth/publish",
            json={
                "object_kind": "pipeline",
                "object_attributes": {
                    "id": 1,
                    "finished_at": datetime.datetime.now().isoformat(),
                    "ref": "v1.0.0",
                },
                "project": {"path_with_namespace": "dummy/dummy"},
            },
            headers={"X-Gitlab-Token": "cde456"},
        )
        self.assertEqual(res.status_code, 200)

    def test_reject_empty_event(self):
        res = self.app.post("/api/projects/deb/publish", json={})
        self.assertEqual(res.status_code, 400)

    def test_reject_invalid_event_data_type(self):
        res = self.app.post("/api/projects/deb/publish", json=[1])
        self.assertEqual(res.status_code, 400)

    def test_reject_invalid_event_type(self):
        res = self.app.post("/api/projects/deb/publish", json={"object_kind": "build"})
        self.assertEqual(res.status_code, 400)


class ErrorReportTest(FlaskTest):
    def test_error_in_hook_triggers_error_report(self):
        with mail.record_messages() as outbox:
            data = {
                "object_kind": "pipeline",
                "object_attributes": {
                    "id": 1,
                    "finished_at": datetime.datetime.now().isoformat(),
                    "ref": "0000000000000000000000000000000000000000",
                },
                "commit": {
                    "author": {"email": "herbert+commit-author@gitlab.localhost"}
                },
                "user": {
                    "name": "Herbert",
                    "email": "herbert@gitlab.localhost",
                },
                "project": {
                    "id": 1,
                    "path_with_namespace": "dummy/dummy",
                    "web_url": "http://gitlab.localhost:31312/dummy/dummy",
                },
                "builds": [
                    {
                        "id": 376,
                        "artifacts_file": {
                            "filename": "artifacts-deb.zip",
                            "size": 1620,
                        },
                    }
                ],
            }
            res = self.app.post("/api/projects/fail-badly/publish", json=data)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(outbox), 1)
            report_message = outbox[0]
            self.assertEqual(
                set(report_message.recipients),
                {"herbert+commit-author@gitlab.localhost", "herbert@gitlab.localhost"},
            )
            self.assertIn("nope", report_message.html)


class PublishToDebRepositoryTest(FlaskTest):
    @patch_dput(inject_mock_as="dput")
    def test_successful_deployment(self, dput: MagicMock):
        test_data = self._load_event("success-tag.json")
        with mail.record_messages() as outbox:
            res = self.app.post("/api/projects/deb/publish", json=test_data)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(outbox), 1)
            mail_html = outbox[0].html
            self.assertIn("Hello Administrator,", css_query_select(mail_html, "header"))
            self.assertIn(
                "deb repository",
                css_query_select(mail_html, "li.is-success .title"),
            )
            self.assertIn(
                "(bleuartd_0.1.0-1_amd64.changes)",
                css_query_select(mail_html, "li.is-success .title"),
            )
            dput.assert_called()

    @patch_dput(fail=True)
    def test_dput_fail_triggers_deployment_error(self):
        test_data = self._load_event("success-tag.json")
        with mail.record_messages() as outbox:
            res = self.app.post("/api/projects/deb/publish", json=test_data)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(outbox), 1)
            mail_html = outbox[0].html
            self.assertIn("Hello Administrator,", css_query_select(mail_html, "header"))
            self.assertIn(
                "deb repository",
                css_query_select(mail_html, "li.is-failure .title"),
            )

    @patch_dput(inject_mock_as="dput")
    def test_skip_deployment_if_not_tagged(self, dput: MagicMock):
        test_data = self._load_event("success-no-tag.json")
        with mail.record_messages() as outbox:
            res = self.app.post("/api/projects/pypi/publish", json=test_data)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(outbox), 0)
            dput.assert_not_called()


class PublishToPythonRepositoryTest(FlaskTest):
    @patch_twine(inject_mock_as="twine")
    def test_successful_deployment(self, twine: MagicMock):
        test_data = self._load_event("success-tag.json")
        with mail.record_messages() as outbox:
            res = self.app.post("/api/projects/pypi/publish", json=test_data)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(outbox), 1)
            mail_html = outbox[0].html
            self.assertIn("Hello Administrator,", css_query_select(mail_html, "header"))
            self.assertIn(
                "python repository",
                css_query_select(mail_html, "li.is-success .title"),
            )
            twine.assert_called()


class MultipleHooksTest(FlaskTest):
    @patch_twine(inject_mock_as="twine")
    @patch_dput(inject_mock_as="dput")
    def test_successful_deployment(self, twine: MagicMock, dput: MagicMock):
        test_data = self._load_event("success-tag.json")
        with mail.record_messages() as outbox:
            res = self.app.post("/api/projects/deb-and-pypi/publish", json=test_data)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(outbox), 1)
            mail_html = outbox[0].html
            self.assertIn("Hello Administrator,", css_query_select(mail_html, "header"))
            self.assertIn(
                "deb repository",
                css_query_select(mail_html, "li.is-success .title"),
            )
            self.assertIn(
                "python repository",
                css_query_select(mail_html, "li.is-success:last-child .title"),
            )
            dput.assert_called()
            twine.assert_called()


class ArtifactTokenTest(FlaskTest):
    @patch_dput(inject_mock_as="dput")
    def test_artifact_download(self, dput: MagicMock):
        test_data = self._load_event("success-tag.json")
        with mail.record_messages() as outbox:
            res = self.app.post(
                "/api/projects/with-gitlab-token/publish", json=test_data
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(outbox), 1)
            mail_html = outbox[0].html
            self.assertIn("error", mail_html)
            dput.assert_not_called()


start_gitlab_mock_server()
