import json
from typing import Any, Callable
from urllib.request import Request, urlopen

from pipedput.typing import GitLabPipelineEvent
from pipedput.utils import get_api_base_url_from_event


class AbstractConstraint:
    def __call__(self, event: GitLabPipelineEvent):
        raise NotImplementedError()

    def __invert__(self):
        return _Not(self)

    def __or__(self, constraint: "AbstractConstraint"):
        return _Or(self, constraint)

    def __and__(self, constraint: "AbstractConstraint"):
        return _And(self, constraint)


class _AbstractConstraintOperator(AbstractConstraint):
    def __init__(self, first_constraint, second_constraint):
        self._first_constraint = first_constraint
        self._second_constraint = second_constraint


class _And(_AbstractConstraintOperator):
    def __call__(self, event: GitLabPipelineEvent):
        return self._first_constraint(event) and self._second_constraint(event)


class _Or(_AbstractConstraintOperator):
    def __call__(self, event: GitLabPipelineEvent):
        return self._first_constraint(event) or self._second_constraint(event)


class _Not(AbstractConstraint):
    def __init__(self, constraint):
        self._constraint = constraint

    def __call__(self, event: GitLabPipelineEvent):
        return not self._constraint(event)


class Callback(AbstractConstraint):
    """only process the event if the callback returned the expected value"""

    def __init__(
        self, callback: Callable[[GitLabPipelineEvent], Any], expect: Any = True
    ) -> None:
        """
        :param callback: the callable to execute when evaluating the constraint
        :param expect: the value that is expected to be returned if the constraint should pass
        """
        super().__init__()
        self._callback = callback
        self._expect = expect

    def __call__(self, event: GitLabPipelineEvent):
        return self._callback(event) == self._expect


class IsProject(AbstractConstraint):
    """only process the event if the project matches the provided name"""

    def __init__(self, project_name_with_namespace: str) -> None:
        """
        :param project_name_with_namespace: the project name with it’s namespace. Something like 'foo/bar'
        """
        super().__init__()
        self._name = project_name_with_namespace

    def __call__(self, event: GitLabPipelineEvent):
        return event["project"]["path_with_namespace"] == self._name


class OnBranch(AbstractConstraint):
    """only process the event if the pipeline is executed for the specified branch"""

    def __init__(self, api_token: str, branch_name: str) -> None:
        super().__init__()
        self._api_token = api_token
        self._branch_name = branch_name

    def __call__(self, event: GitLabPipelineEvent):
        return self._is_commit_contained_in_ref(event, self._branch_name)

    def _is_commit_contained_in_ref(self, event, ref_name: str):
        base_url = get_api_base_url_from_event(event)
        project_id = event["project"]["id"]
        commit_sha = event["commit"]["id"]
        commit_url = (
            f"{base_url}/projects/{project_id}/repository/commits/{commit_sha}/refs"
        )
        request = Request(commit_url, headers={"PRIVATE-TOKEN": self._api_token})
        with urlopen(request) as response:
            data = json.load(response)
        return any(
            [ref["type"] == "branch" and ref["name"] == ref_name for ref in data]
        )


class OnDefaultBranch(OnBranch):
    """only process the event if the pipeline is executed for the default branch of this project"""

    def __init__(self, api_token: str) -> None:
        # self.branch_name should never be used, but just to be sure we use
        # a branch_name that is not valid under the git ref name rules
        super().__init__(api_token, ":DEFAULT:")

    def __call__(self, event: GitLabPipelineEvent):
        return self._is_commit_contained_in_ref(
            event, event["project"]["default_branch"]
        )


class IsTag(AbstractConstraint):
    """only process the event if the pipeline is executed for a tag"""

    def __call__(self, event: GitLabPipelineEvent):
        return event["object_attributes"]["tag"] is True


class WasSuccessful(AbstractConstraint):
    """only process the event if the pipeline was successful"""

    def __call__(self, event: GitLabPipelineEvent):
        return event["object_attributes"]["status"] == "success"


class WasManuallyTriggered(AbstractConstraint):
    """only process the event if the pipeline was manually triggered"""

    def __init__(self, require=any):
        super().__init__()
        self._require = require

    def __call__(self, event: GitLabPipelineEvent):
        if isinstance(self._require, str):
            for build in event["builds"]:
                if build["name"] == self._require:
                    return build["manual"]
            return False
        else:
            return self._require(build["manual"] for build in event["builds"])
