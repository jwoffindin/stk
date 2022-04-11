setup:
	python3 -m venv .venv
	python3 -m pip install --upgrade pip setuptools wheel
	source .venv/bin/activate && python3 -m pip install -r requirements.txt

build:
	python3 -m pip install -q build