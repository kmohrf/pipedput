from typing import Callable, Iterator, List, Mapping, Optional, Protocol, TypedDict


class GitLabAuthor(TypedDict):
    name: str
    email: str


class GitLabUser(GitLabAuthor):
    id: int
    username: str
    avatar_url: Optional[str]


class GitLabVariable(TypedDict):
    key: str
    value: str


class GitLabPipelineObjectAttributes(TypedDict):
    id: str
    ref: str
    tag: bool
    sha: str
    before_sha: str
    source: str
    status: str
    detailed_status: str
    stages: List[str]
    created_at: str
    finished_at: str
    duration: int
    variables: List[GitLabVariable]


class GitLabRunner(TypedDict):
    id: int
    description: str
    active: bool
    is_shared: bool
    tags: List[str]


class GitLabArtifactsFile(TypedDict):
    filename: Optional[str]
    size: Optional[int]


class GitLabBuild(TypedDict):
    id: int
    stage: str
    name: str
    status: bool
    created_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    when: str
    manual: bool
    allow_failure: bool
    user: GitLabUser
    runner: Optional[GitLabRunner]
    artifacts_file: GitLabArtifactsFile
    environment: Optional[Mapping[str, str]]


class GitLabCommit(TypedDict):
    id: str
    message: str
    title: str
    timestamp: str
    url: str
    author: GitLabAuthor


class GitLabProject(TypedDict):
    id: int
    name: str
    description: str
    web_url: str
    avatar_url: Optional[str]
    git_ssh_url: str
    git_http_url: str
    namespace: str
    visibility_level: int
    path_with_namespace: str
    default_branch: str
    ci_config_path: Optional[str]


class GitLabMergeRequest(TypedDict):
    id: int
    iid: int
    title: str
    source_branch: str
    source_project_id: int
    target_branch: str
    target_project_id: int
    state: str
    merge_status: str
    url: str


class GitLabEvent(TypedDict):
    object_kind: str


class GitLabPipelineEvent(GitLabEvent):
    object_attributes: GitLabPipelineObjectAttributes
    merge_request: Optional[GitLabMergeRequest]
    user: GitLabUser
    project: GitLabProject
    commit: GitLabCommit
    builds: List[GitLabBuild]


class DeploymentStateLike(Protocol):
    target_name: str
    was_successful: bool
    notify: bool
    asset: Optional[str] = None
    exc: Optional[Exception] = None
    error: Optional[str] = None


class HookLike(Protocol):
    name: str

    def should_execute_for(self, event: GitLabPipelineEvent) -> bool:
        ...

    def __call__(
        self, event: GitLabPipelineEvent, artifact_directory: str
    ) -> Iterator[DeploymentStateLike]:
        ...


Constraint = Callable[[GitLabPipelineEvent], bool]
