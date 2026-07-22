.PHONY: run test

run:
	python3 scripts/run.py

test:
	python3 -m unittest discover -s tests -v
