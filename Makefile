setup:
	python3 -m venv .venv
	python3 -m pip install --upgrade pip setuptools wheel
	python3 -m pip install -q build
	source .venv/bin/activate && python3 -m pip install -r requirements.txt

build:
	python3 -m build

test:
	source .venv/bin/activate && pytest .