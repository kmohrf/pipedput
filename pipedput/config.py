import enum
from .utils import process_artifact, get_artifact_urls, invoke_all


class EventProcessEvent(enum.Enum):
    ON_PUBLISH = 'PUBLISH'


class ProjectConfig:
    def __init__(self, name, dput_config, token=None, artifact_token=None) -> None:
        self.project_name = name
        self.dput_config = dput_config
        self.token = token
        self.artifact_token = artifact_token
        self.constraints = []
        self.hooks = []

    def should_process(self, event):
        return all([constraint(event) for constraint in self.constraints])

    def process(self, event):
        if self.should_process(event):
            for artifact in get_artifact_urls(event):
                for change, was_successful in process_artifact(artifact, self.dput_config,
                                                               self.artifact_token):
                    payload = {
                        'project': self.project_name,
                        'source': event,
                        'artifact_url': artifact,
                        'change': change,
                        'was_successful': was_successful,
                    }
                    invoke_all(self.hooks, None, EventProcessEvent.ON_PUBLISH, payload)
                    yield payload

    def add_constraint(self, *constraints):
        for constraint in constraints:
            self.constraints.append(constraint)
        return self

    def on(self, callback, only_event: EventProcessEvent = None):
        def _callback(event, payload):
            if only_event is None or event is only_event:
                callback(payload)
        self.hooks.append(_callback)
