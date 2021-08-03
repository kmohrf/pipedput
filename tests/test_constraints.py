from os.path import join
import unittest
from unittest.mock import MagicMock, patch
import warnings

from pipedput.constraints import (
    Callback,
    IsProject,
    IsTag,
    OnBranch,
    OnDefaultBranch,
    WasManuallyStarted,
    WasSuccessful,
)
from tests.utils import TestFileMock

default_commit_ref = TestFileMock(
    join("commit-refs", "583972aba628265857e551ebeb3b58293c060591.json")
)


class ConstraintTest(unittest.TestCase):
    def test_callback_constraint(self):
        mock = MagicMock(return_value=4)
        cb = Callback(mock, 4)
        self.assertTrue(cb("hello"))
        mock.assert_called_once_with("hello")
        mock = MagicMock(return_value=6)
        cb = Callback(mock, 4)
        self.assertFalse(cb("hello"))

    def test_is_project_constraint(self):
        is_foo_bar = IsProject("foo/bar")
        self.assertTrue(is_foo_bar({"project": {"path_with_namespace": "foo/bar"}}))
        self.assertFalse(
            is_foo_bar({"project": {"path_with_namespace": "foo-bar/baz"}})
        )

    def test_is_tag_constraint(self):
        is_tag = IsTag()
        self.assertTrue(is_tag({"object_attributes": {"tag": True}}))
        self.assertFalse(is_tag({"object_attributes": {"tag": False}}))

    @patch("pipedput.constraints.urlopen", default_commit_ref)
    def test_on_branch_constraint(self):
        event = {
            "commit": {
                "id": "583972aba628265857e551ebeb3b58293c060591",
            },
            "project": {
                "id": 1,
                "web_url": "http://gitlab.localhost:31312/dummy/dummy",
            },
        }
        is_on_main_branch = OnBranch("test-token", "main")
        is_on_foo_branch = OnBranch("test-token", "foo")
        self.assertTrue(is_on_main_branch(event))
        self.assertFalse(is_on_foo_branch(event))

    @patch("pipedput.constraints.urlopen", default_commit_ref)
    def test_on_default_branch_constraint(self):
        event_1 = {
            "commit": {
                "id": "583972aba628265857e551ebeb3b58293c060591",
            },
            "project": {
                "id": 1,
                "web_url": "http://gitlab.localhost:31312/dummy/dummy",
                "default_branch": "main",
            },
        }
        event_2 = {
            "commit": {
                "id": "583972aba628265857e551ebeb3b58293c060591",
            },
            "project": {
                "id": 1,
                "web_url": "http://gitlab.localhost:31312/dummy/dummy",
                "default_branch": "foo",
            },
        }
        is_on_default_branch = OnDefaultBranch("test-token")
        self.assertTrue(is_on_default_branch(event_1))
        self.assertFalse(is_on_default_branch(event_2))

    def test_was_manually_started_constraint(self):
        # test any
        was_manually_started = WasManuallyStarted()
        self.assertTrue(was_manually_started({"builds": [{"manual": True}]}))
        self.assertFalse(was_manually_started({"builds": [{"manual": False}]}))

        # test all
        was_manually_started = WasManuallyStarted(all)
        self.assertTrue(
            was_manually_started({"builds": [{"manual": True}, {"manual": True}]})
        )
        self.assertFalse(
            was_manually_started({"builds": [{"manual": True}, {"manual": False}]})
        )

        # test specific build
        was_manually_started = WasManuallyStarted("foo")
        self.assertTrue(
            was_manually_started({"builds": [{"name": "foo", "manual": True}]})
        )
        self.assertFalse(
            was_manually_started({"builds": [{"name": "foo", "manual": False}]})
        )
        self.assertFalse(was_manually_started({"builds": []}))

    def test_was_manually_triggered_constraint(self):
        try:
            from pipedput.constraints import WasManuallyTriggered
        except ImportError:
            self.fail(
                "WasManuallyTriggered constraint should exist in pipedput.constraints package."
            )
        else:
            self.assertTrue(issubclass(WasManuallyTriggered, WasManuallyStarted))
        with warnings.catch_warnings(record=True) as catched_warnings:
            WasManuallyTriggered()
        self.assertEqual(len(catched_warnings), 1)
        self.assertTrue(issubclass(catched_warnings[-1].category, DeprecationWarning))
        self.assertIn("deprecated", str(catched_warnings[-1].message))

    def test_was_successful_constraint(self):
        was_successful = WasSuccessful()
        self.assertTrue(was_successful({"object_attributes": {"status": "success"}}))
        self.assertFalse(was_successful({"object_attributes": {"status": "failed"}}))

    def test_logical_and(self):
        was_successful_and_is_tag = WasSuccessful() & IsTag()
        self.assertTrue(
            was_successful_and_is_tag(
                {"object_attributes": {"status": "success", "tag": True}}
            )
        )
        self.assertFalse(
            was_successful_and_is_tag(
                {"object_attributes": {"status": "success", "tag": False}}
            )
        )
        self.assertFalse(
            was_successful_and_is_tag(
                {"object_attributes": {"status": "failed", "tag": True}}
            )
        )

    def test_logic_or(self):
        was_successful_and_is_tag = WasSuccessful() | IsTag()
        self.assertTrue(
            was_successful_and_is_tag(
                {"object_attributes": {"status": "success", "tag": True}}
            )
        )
        self.assertTrue(
            was_successful_and_is_tag(
                {"object_attributes": {"status": "success", "tag": False}}
            )
        )
        self.assertTrue(
            was_successful_and_is_tag(
                {"object_attributes": {"status": "failed", "tag": True}}
            )
        )
        self.assertFalse(
            was_successful_and_is_tag(
                {"object_attributes": {"status": "failed", "tag": False}}
            )
        )

    def test_logical_not(self):
        was_not_successful = ~WasSuccessful()
        self.assertFalse(
            was_not_successful({"object_attributes": {"status": "success"}})
        )
        self.assertTrue(was_not_successful({"object_attributes": {"status": "failed"}}))
