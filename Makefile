VERSION := $(shell ./setup.py --version)
IS_FINAL := $(shell echo $VERSION | egrep -x '([0-9]{1,}\.){2}[0-9]{1,}')
default:
	@echo "$(VERSION) try 'make setup test'"

setup:
	python3 -m venv .venv
	python3 -m pip install --upgrade pip setuptools wheel
	python3 -m pip install -q build
	source .venv/bin/activate && python3 -m pip install -r ./dev-requirements.txt .

build:
	python3 -m build

test:
	source .venv/bin/activate && pytest .

test_loop:
	source .venv/bin/activate && ptw --runner "pytest --picked --testmon --maxfail=1"

docker-build:
	docker build --build-arg VERSION=$(VERSION) -t johnwo/stk:$(VERSION) .

docker-run:
	docker run --rm -it -v ~/.aws:/root/.aws -v ${TEMPLATE_PATH}:/templates -v ${CONFIG_PATH}:/config johnwo/stk:latest bash

untag:
	git push origin :refs/tags/$(VERSION) ||:
	git tag -d $(VERSION)

ifeq ($(shell git status --porcelain),)
tag:
	test $(shell git branch --show-current) == "main"
	git tag -s -a $(VERSION) -m 'release version $(VERSION)'
	git push origin $(VERSION)

release: tag docker-build
	docker push johnwo/stk:$(VERSION)
ifneq ($(IS_FINAL),)
	docker tag johnwo/stk:$(VERSION) johnwo/stk:latest
	docker push johnwo/stk:latest
endif
else
release:
	@echo "Git repository is dirty"
endif

.PHONY: default setup build test test_loop tag release docker-build docker-run docker-release
