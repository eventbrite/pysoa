# To run a release, commit the version bump commit with the version in its commit message then
# run "make release version=1.2.3"

.PHONY: release

all:

release:
ifndef version
	$(error Please supply a version)
endif
	@echo Releasing version $(version)
ifeq (,$(findstring $(version),$(shell git log --oneline -1)))
	$(error Last commit does not match version)
endif
	git tag $(version)
	git push
	git push --tags
	python setup.py sdist bdist_wheel upload
