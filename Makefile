VERSION := $(shell ./setup.py --version)

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

ifeq ($(shell git status --porcelain),)
tag:
	test $(shell git branch --show-current) == "main"
	git tag -a $(VERSION) -m 'release version $(VERSION)'
	git push origin $(VERSION)

release: tag docker-build
	docker tag johnwo/stk:latest johnwo/stk:$(VERSION)
	docker push johnwo/stk:latest
	docker push johnwo/stk:$(VERSION)
endif

.PHONY: default setup build test test_loop tag release docker-build docker-run docker-release
