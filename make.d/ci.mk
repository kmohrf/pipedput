DOCKER_REGISTRY = git-registry.hack-hro.de:443/kmohrf/pipedput
DOCKER_ARGS ?=
CI_BUILD_IMAGE_PATH = docker/build/Dockerfile
CI_BUILD_IMAGE_NAME = build:buster
CI_BUILD_IMAGE = $(DOCKER_REGISTRY)/$(CI_BUILD_IMAGE_NAME)

.PHONY: ci-image
ci-image:
	docker build $(DOCKER_ARGS) --tag "$(CI_BUILD_IMAGE)" --file "$(CI_BUILD_IMAGE_PATH)" .

.PHONY: ci-image-push
ci-image-push:
	docker push "$(CI_BUILD_IMAGE)"

.PHONY: ci-docker-login
ci-docker-login:
	docker login "$(DOCKER_REGISTRY)"
