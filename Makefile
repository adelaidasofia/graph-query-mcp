# Canonical CI gate. `make ci` is the ONE command both CI (test.yml, auto-
# managed by gh-harden-repos.sh) and the local pre-push gate (ci-test) run,
# so they cannot drift. Mirrors the test job: pytest tests/ -v, tolerating
# exit 5 (no tests collected) exactly as the auto-managed workflow does.
.PHONY: ci
ci:
	pytest tests/ -v || [ $$? -eq 5 ]
