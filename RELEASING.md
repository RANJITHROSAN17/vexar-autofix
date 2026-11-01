# Coordinated first release (issue #2 / G8)

## Required order — do not skip the parent publication

1. Review and merge the Vexar-MCP namespace migration for **0.3.0**. It moves the
   implementation to `vexar_mcp`, retaining `mcp_doctor` aliases for 0.3.x only.
2. Configure the parent project's PyPI Trusted Publisher and `pypi` GitHub
   environment, then publish its `v0.3.0` tag through its existing release workflow.
   Verify the public package is available; a built local wheel is not publication.
3. Only after Vexar-MCP 0.3.0 is on PyPI, merge this repository's canonical-import
   and version-pin update. Its ordinary CI installs the published dependency and
   deliberately has no Git fallback.
4. Configure a PyPI pending publisher for `vexar-autofix`: owner
   `RANJITHROSAN17`, repository `vexar-autofix`, workflow `publish-pypi.yml`,
   environment `pypi`. Configure the matching GitHub environment and approvals.
   This requires the maintainer's PyPI account; GitHub repository access is not
   sufficient to register a PyPI publisher.
5. On the reviewed merge commit, create and push tag `v0.1.0`. The release workflow
   verifies version agreement, tests, mock eval, wheel/sdist validity and a clean
   wheel install with the public parent dependency before requesting an OIDC upload.

Do not tag an unmerged development branch or publish a VCS dependency to work around
an unavailable scanner release. The public pin in `pyproject.toml` intentionally
fails until step 2 is complete. Before publication this change remains release-blocked,
not a completed first PyPI release.

## Verify after publication

In a new virtual environment:

```bash
python -m pip install vexar-mcp==0.3.0 vexar-autofix==0.1.0
python scripts/check_release_install.py
vexar-mcp --version
vexar-autofix --help
```

The install checker asserts the scanner version and dependency metadata and compares
both installed distributions' complete file lists for overlap. Their canonical
namespaces are `vexar_mcp` and `vexar_autofix`. The parent's temporary `mcp_doctor`
shim is not used here; it still conflicts with the *unrelated* `mcp-doctor`
distribution, so do not install that third package during the shim minor series.

## Test the candidate wheels before publication (not proof of a PyPI release)

Build the parent and this project with `python -m build`. In a clean environment,
install both wheels together from a directory containing those two wheels, using
`pip install --no-index --find-links <wheel-directory> vexar-mcp==0.3.0 vexar-autofix==0.1.0`,
then run `scripts/check_release_install.py`. This proves packaging compatibility;
public-index availability must still be checked after publication.
