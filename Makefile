PYTHON=python3

all: build

build:
	$(PYTHON) -m pip wheel --no-deps -w dist .
test:
	$(PYTHON) runtests.py
clean:
	find . -name '*.py[co]' -exec rm -f "{}" ';'
	find . -name '__pycache__' -type d -prune -exec rm -rf "{}" ';'
	find ./dnuos/locale -name '*.mo' -exec rm -f "{}" ';'
	rm -rf build dist dnuos.egg-info temp
install:
	$(PYTHON) -m pip install .
