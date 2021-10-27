import shutil

from pipedput.constraints import AbstractConstraint
from pipedput.hooks import GenericGlobHook
from pipedput.typing import GitLabPipelineEvent


# You can define new constraints with relative ease...
class IsUser(AbstractConstraint):
    """only process the event if the specified user triggered it"""

    def __init__(self, username: str):
        super().__init__()
        self._username = username

    def __call__(self, event: GitLabPipelineEvent):
        return event["user"]["username"] == self._username


# ... or even hooks!
class BackupJPEGs(GenericGlobHook):
    DEFAULT_NAME = "copy JPEGs"
    GLOB_PATTERN = "**/*.jpeg"
    BACKUP_DIR = "/var/backups/jpegs"

    def _handle_artifact(
        self,
        event: GitLabPipelineEvent,
        artifact_path: str,
        artifact_name: str,
        **kwargs,
    ):
        try:
            shutil.copy(artifact_path, self.BACKUP_DIR)
        except PermissionError:
            yield self._error(asset=artifact_name)
        else:
            yield self._success(asset=artifact_name)
