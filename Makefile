VERSION := $(shell PYTHONPATH=. python -c 'import stk;print(stk.VERSION)')
IS_FINAL := $(shell PYTHONPATH=. python -c 'import stk;print(stk.VERSION)' | egrep -x '([0-9]{1,}\.){2}[0-9]{1,}')
default:
	@echo "$(VERSION) try 'make setup test'"

setup:
	python3 -m venv .venv
	python3 -m pip install --upgrade pip
	source .venv/bin/activate && python3 -m pip install -r ./dev-requirements.txt setuptools wheel twine build

test:
	source .venv/bin/activate && pytest .

test-loop:
	source .venv/bin/activate && ptw --runner "pytest --picked --testmon --maxfail=1"

pip-package:
	rm -rf dist build
	source .venv/bin/activate && python3 -m build

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

release: tag pip-release docker-release

pip-release: pip-package
ifneq ($(IS_FINAL),)
	source .venv/bin/activate && python3 -m twine upload --repository pypi dist/*
else
	echo "Not publishing to pypi - not final release $(IS_FINAL)/$(VERSION)"
endif

docker-release: docker-build
	docker push johnwo/stk:$(VERSION)
ifneq ($(IS_FINAL),)
	docker tag johnwo/stk:$(VERSION) johnwo/stk:latest
	docker push johnwo/stk:latest
else
	docker tag johnwo/stk:$(VERSION) johnwo/stk:unstable
	docker push johnwo/stk:unstable
endif
else
release:
	@echo "Git repository is dirty"
endif

.PHONY: default setup build test test-loop pip-package tag release pip-release docker-build docker-run docker-release
