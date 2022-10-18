TAG_COMMIT := $(shell git rev-list --abbrev-commit --tags --max-count=1)
TAG := $(shell git describe --abbrev=0 --tags ${TAG_COMMIT} 2>/dev/null || true)
VERSION := $(TAG:v%=%)
ifneq ($(shell git status --porcelain),)
    VERSION := $(VERSION)-dirty
endif

default:
	@echo "$(VERSION) try 'make setup test'"

setup:
	python3 -m venv .venv
	python3 -m pip install --upgrade pip setuptools wheel
	python3 -m pip install -q build
	source .venv/bin/activate && python3 -m pip install -r requirements.txt

build:
	python3 -m build

test:
	source .venv/bin/activate && pytest .

test_loop:
	source .venv/bin/activate && ptw --runner "pytest --picked --testmon --maxfail=1"

docker-build:
	docker build --build-arg VERSION=$(VERSION) -t johnwo/stk .

docker-run:
	docker run --rm -it -v ~/.aws:/root/.aws -v ${TEMPLATE_PATH}:/templates -v ${CONFIG_PATH}:/config johnwo/stk:latest bash

docker-release: docker-build
	docker tag johnwo/stk:latest johnwo/stk:$(VERSION)
	docker push johnwo/stk:latest
	docker push johnwo/stk:$(VERSION)

.PHONY: default setup build test test_loop docker-build docker-run docker-release
