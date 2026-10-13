# Contributing

Read [README.md](./README.md) for the action's inputs, outputs, and usage examples.

## Setup

1. Clone your fork and open a terminal in the repository root.
2. Install Python 3.12 to match CI.

This is a composite GitHub Action defined in [action.yml](./action.yml), with a
Python installer in [install.py](./install.py). The installer and tests use only
the Python standard library, so no dependency installation or build step is needed.

## Checks

Run the installer unit tests from the repository root:

```sh
python -m unittest discover -s tests -v
```

The unit tests use mocked downloads and temporary files. They need no network
access or credentials.

Pull requests also run these CI checks:

- [Installer and MCP tests](./.github/workflows/setup-stackql-mcp-test.yml) run
  across Linux, Windows, macOS, and Windows ARM64, using `latest` and pinned
  StackQL releases. They check the action outputs and run
  [scripts/smoke-test.py](./scripts/smoke-test.py) through the emitted MCP config.
  These integration checks need network access but no secrets.
- [Workflow linting](./.github/workflows/actionlint.yml) runs actionlint 1.7.12
  with ShellCheck on `.github/workflows/*.yml` and `examples/*.yml`. For workflow
  or example changes, the workflow contains the Docker command to run locally
  from Bash.

## Pull requests

- Keep changes scoped to one coherent fix or feature.
- Include tests with functional changes and describe the checks you ran.
- Update `README.md` and relevant examples when changing inputs, outputs, or usage.
- Preserve the `read_only` default and downloaded bundle checksum verification.
- Report vulnerabilities privately as described in [SECURITY.md](./SECURITY.md),
  including findings involving third-party servers.
