include makefilet-download-ondemand.mk

default-target: build

distribute-pypi:
	@if ! which twine >/dev/null 2>&1 || [ "$$(printf "1.11.0\n$$(twine --version | head -1 | cut -d" " -f3)" | sort -V | head -1)" != "1.11.0" ]; then \
		echo "you need twine >v1.11.0" >&2; \
		exit 1; \
	fi
	rm -rf dist/
	python3 setup.py sdist
	twine upload dist/*
