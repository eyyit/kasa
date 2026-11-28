.PHONY: check test

check: test

test:
	python3 -B -m unittest discover -s . -p '*_test.py' -v
