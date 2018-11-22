import os
from flask import Flask, jsonify, request
from .utils import invoke_all, flatten, pick

app = Flask('pipedput')
config_file = os.environ.get('PIPEDPUT_CONFIG_FILE', None)
if config_file is None:
    raise ImportError('please set the PIPEDPUT_CONFIG_FILE environment variable')
if not os.path.isabs(config_file):
    raise ImportError('please provide an absolute path for the config file')
app.config.from_pyfile(os.path.realpath(config_file))


def is_allowed(project_name, token):
    project = None

    for config in app.config['PROJECT_CONFIGS']:
        if config.project_name == project_name:
            project = config
            break

    if project is None:
        return False

    return project.token is None or project.token == token


@app.route('/api/projects/<project>/publish', methods=['POST'])
def publish_artifact(project):
    payload = request.json

    if not is_allowed(project, request.headers.get('X-Gitlab-Token', None)):
        return 'You’re not allowed to publish projects', 403

    if payload['object_kind'] != 'pipeline':
        return 'Only pipeline events will be processed', 400

    published_artifacts = flatten(invoke_all(app.config['PROJECT_CONFIGS'], 'process', payload))

    return jsonify({
        'data': {
            'published_artifacts': [
                pick(artifact, 'project', 'change', 'was_successful')
                for artifact in published_artifacts
            ],
        }
    }), 200


if __name__ == '__main__':
    app.run()
