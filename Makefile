## ==> DipDup makefile
.ONESHELL:
.PHONY: test build docs
.DEFAULT_GOAL: all

##
## DEV=1           Install dev dependencies
DEV=1
## PLUGINS=""      Install extras (`pytezos` only)
PLUGINS=""
## TAG=latest      Docker tag for images built
TAG=latest
##

all:            ## Run a whole CI pipeline (default)
	make install lint test cover

install:        ## Install project
	poetry install \
	`if [ -n "${PLUGINS}" ]; then for i in ${PLUGINS}; do echo "-E $$i "; done; fi` \
	`if [ "${DEV}" = "0" ]; then echo "--no-dev"; fi`

lint:           ## Lint with all tools
	make isort black flake mypy

isort:          ## Lint with isort
	poetry run isort src tests

black:          ## Lint with black
	poetry run black src tests

flake:          ## Lint with flake8
	poetry run flakehell lint src tests

mypy:           ## Lint with mypy
	poetry run mypy src tests

test:           ## Run test suite
	poetry run pytest --cov-report=term-missing --cov=dipdup --cov-report=xml -n auto --dist loadscope -s -v tests

cover:          ## Print coverage for the current branch
	poetry run diff-cover coverage.xml

build:          ## Build wheel Python package
	poetry build

image:          ## Build Docker image
	docker build . -t dipdup:${TAG}
	docker build . -t dipdup:${TAG}-pytezos --build-arg PLUGINS=pytezos

release-patch:  ## Release patch version
	bumpversion patch
	git push --tags
	git push

release-minor:  ## Release minor version
	bumpversion minor
	git push --tags
	git push

release-major:  ## Release major version
	bumpversion major
	git push --tags
	git push

docs:           ## Build config/CLI references and copy to ../dipdup-docs
	cd docs; rm -r _build; make install

help:           ## Show this help
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'