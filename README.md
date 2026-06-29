[![setup stackql mcp test](https://github.com/stackql/setup-stackql-mcp/actions/workflows/setup-stackql-mcp-test.yml/badge.svg)](https://github.com/stackql/setup-stackql-mcp/actions/workflows/setup-stackql-mcp-test.yml)
[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-Setup%20StackQL%20MCP-blue?logo=github)](https://github.com/marketplace/actions/setup-stackql-mcp-server)
[![StackQL](https://stackql.io/img/stackql-logo-bold.png)](https://github.com/stackql/stackql)

# setup-stackql-mcp

Installs the signed [StackQL](https://stackql.io) binary (sha256-verified against the release checksums) and emits an `mcpServers` JSON config that plugs straight into MCP-capable actions like [anthropics/claude-code-action](https://github.com/anthropics/claude-code-action). This gives CI agents live SQL query (and, when you raise the mode, provisioning) access to AWS, Azure, Google, GitHub, Databricks, and 40+ other providers over the Model Context Protocol. It defaults to `read_only` server mode - the safe default for agentic CI.

## setup-stackql vs setup-stackql-mcp

Pick the right action for the job:

- [`setup-stackql`](https://github.com/stackql/setup-stackql) installs the StackQL CLI for running queries directly (plain `stackql exec` steps).
- `setup-stackql-mcp` (this repo) installs the same binary **and** configures it as an MCP server, emitting an `mcp-config` output for AI agent actions. Use this for agentic workflows; use `setup-stackql` for plain `stackql exec` steps.

You can still call the binary directly with this action - it is added to `PATH` - so if a workflow does both agent and non-agent steps, this one action covers both (see [examples/use-binary-directly.yml](examples/use-binary-directly.yml)).

## Inputs

| Input | Default | Description |
|---|---|---|
| `version` | `latest` | stackql release version (`X.Y.Z`) or `latest` |
| `mode` | `read_only` | MCP server mode: `read_only`, `safe`, `delete_safe`, `full_access` |
| `auth` | (none) | stackql `--auth` JSON for provider credentials |
| `bundle-path` | (none) | install from a local `.mcpb` instead of downloading - used by this repo's own CI, not by end users |

## Outputs

| Output | Description |
|---|---|
| `binary-path` | absolute path to the installed stackql binary |
| `mcp-config` | `mcpServers` JSON string |
| `mcp-config-file` | path to the same JSON, written to a file under `$RUNNER_TEMP` |

Two forms of the same config, for two consumption styles. The emitted JSON nests an escaped JSON string (the `mcpServers.stackql.args` array carries `--mcp.config {"server":...}` as a value), so it is JSON-with-JSON, double-escaped - exactly the payload that makes inline shell interpolation fragile.

- Use `mcp-config-file` whenever the config reaches a shell or a CLI parser - which includes `anthropics/claude-code-action` (its `claude_args: --mcp-config <path>` feeds the `claude` CLI) and any direct `claude --mcp-config` call. The file path sidesteps the escaping problem. This is the default in the examples below.
- Use `mcp-config` (the string) only for a consumer whose `with:` input takes the JSON directly, where GitHub interpolates the value with no shell involved. Note: `claude-code-action` v1 has no such `mcp_config` input - it routes everything through `claude_args` - so for that action you always want the file.

The action also exports `STACKQL_MCP_BIN` to the job env (the [`@stackql/mcp-server`](https://www.npmjs.com/package/@stackql/mcp-server) npm and [`stackql-mcp-server`](https://pypi.org/project/stackql-mcp-server/) PyPI wrappers detect it and skip their own download) and adds the install dir to `PATH`.

It runs on `ubuntu-latest`, `windows-latest`, and `macos-latest` runners (linux-x64, linux-arm64, windows-x64, darwin-universal).

## Quick start

The smallest useful workflow - no cloud credentials, only an Anthropic API key. The github provider runs in `null_auth` mode, which reads public data with no token.

```yaml
name: org-posture
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  posture:
    runs-on: ubuntu-latest
    steps:
      - id: stackql
        uses: stackql/setup-stackql-mcp@v1
        with:
          auth: '{"github":{"type":"null_auth"}}'

      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: |
            Using stackql, list the public repositories in the stackql org and
            summarise them as a markdown table.
          claude_args: |
            --mcp-config ${{ steps.stackql.outputs.mcp-config-file }}
            --allowedTools 'mcp__stackql__*'
```

Wiring into `claude-code-action` (v1) is two flags inside `claude_args`: `--mcp-config` takes the path from `mcp-config-file`, and `--allowedTools 'mcp__stackql__*'` lets the agent call the stackql tools. Pass the file, not the `mcp-config` string - `claude_args` is parsed as CLI arguments, and the file avoids the double-escaped-JSON quoting trap. The MCP tool-allowlist convention is `mcp__<server-name>__<tool>`; the server name here is `stackql`, so `mcp__stackql__*` allows all of them.

## Examples

Each example below is also a runnable file under [examples/](examples/) - copy it into your repo's `.github/workflows/`. They all use `mode: read_only` and scope `allowedTools` to the stackql server.

### 1. Nightly cloud security audit -> GitHub issue (AWS)

Full file: [examples/nightly-cloud-audit.yml](examples/nightly-cloud-audit.yml). Needs secrets `ANTHROPIC_API_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.

```yaml
name: nightly-cloud-audit
on:
  schedule:
    - cron: "0 18 * * *"
  workflow_dispatch:
permissions:
  contents: read
  issues: write
jobs:
  audit:
    runs-on: ubuntu-latest
    # Cloud credentials are for the stackql MCP server, not for Claude. The agent
    # step spawns the server as a child process, so it inherits these job-level
    # vars; stackql picks up the standard AWS_* env vars implicitly (no auth:
    # input needed). Claude only speaks MCP.
    env:
      AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
      AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    steps:
      - id: stackql
        uses: stackql/setup-stackql-mcp@v1
        with:
          mode: read_only

      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: |
            Using the stackql tools, audit our AWS account for: S3 buckets without
            encryption or with public access, security groups open to 0.0.0.0/0 on
            sensitive ports, and IAM users without MFA. Open a GitHub issue
            "Cloud audit <date>" summarising findings WITH the SQL you ran as
            evidence. If nothing is found, do not open an issue.
          claude_args: |
            --mcp-config ${{ steps.stackql.outputs.mcp-config-file }}
            --allowedTools 'mcp__stackql__*'
```

### 2. PR cost estimate from a Terraform plan (Google)

Full file: [examples/pr-cost-check.yml](examples/pr-cost-check.yml). Needs secrets `ANTHROPIC_API_KEY`, `GCP_SA_KEY`, and a `terraform/plan.json` in the PR.

```yaml
name: pr-cost-check
on: pull_request
permissions:
  contents: read
  pull-requests: write
jobs:
  cost:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - run: echo '${{ secrets.GCP_SA_KEY }}' > /tmp/sa.json
      - id: stackql
        uses: stackql/setup-stackql-mcp@v1
        with:
          auth: '{"google":{"type":"service_account","credentialsfilepath":"/tmp/sa.json"}}'

      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: |
            Read terraform/plan.json in this PR. Using stackql pricing tools,
            estimate the monthly cost of the resources being created and post a PR
            comment with a per-resource breakdown and total.
          claude_args: |
            --mcp-config ${{ steps.stackql.outputs.mcp-config-file }}
            --allowedTools 'mcp__stackql__*'
```

### 3. Zero-secrets starter: GitHub org posture

Full file: [examples/org-posture.yml](examples/org-posture.yml). The only secret it needs is `ANTHROPIC_API_KEY` - the github provider runs in `null_auth` mode (no token).

```yaml
name: org-posture
on:
  workflow_dispatch:
permissions:
  contents: read
  issues: write
jobs:
  posture:
    runs-on: ubuntu-latest
    steps:
      - id: stackql
        uses: stackql/setup-stackql-mcp@v1
        with:
          auth: '{"github":{"type":"null_auth"}}'

      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: |
            Using stackql, list the public repositories in the stackql org and
            summarise their posture as a markdown table: visibility, archived
            state, license, open issue count, and last push. Flag any that look
            unmaintained.
          claude_args: |
            --mcp-config ${{ steps.stackql.outputs.mcp-config-file }}
            --allowedTools 'mcp__stackql__*'
```

`null_auth` reads public data only. For private repos or branch-protection details, supply a token via stackql's github `basic` auth (username + token env vars); note the built-in `GITHUB_TOKEN` is scoped to the current repo, so org-wide reads across other repos need a PAT or GitHub App token with org read. See the note at the bottom of [examples/org-posture.yml](examples/org-posture.yml).

### 4. Use the binary directly (no agent)

Full file: [examples/use-binary-directly.yml](examples/use-binary-directly.yml).

```yaml
      - uses: stackql/setup-stackql-mcp@v1
      - run: |
          stackql exec "REGISTRY PULL github"
          stackql exec "SHOW SERVICES IN github"
```

## Provider credentials

stackql reads provider credentials from standard environment variables - the same ones Terraform and the provider SDKs already look for (for example `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, `ARM_CLIENT_ID`/`ARM_CLIENT_SECRET`, and so on across 40+ providers). Source them from GitHub Actions secrets at the job level so they live in the stackql MCP server's context; the server uses them to call the remote provider on the agent's behalf. Claude never handles the credentials - it only speaks MCP to the server.

Because of this, most providers need no `auth:` input at all - just make the standard env vars available to the job. Set `auth:` only to point stackql at something non-standard, such as a service-account key file path or `null_auth` for public, credential-free reads (see the [examples](examples/)).

## Security

An agent with SQL access over your cloud and SaaS estate has real blast radius. The defaults are built to contain it; keep them that way unless you have a reason not to.

- **`read_only` is the default.** In `read_only` mode the agent can query providers but cannot mutate them, regardless of what a prompt (or a prompt-injection payload pulled in from issue text, a PR, or a third-party API response) tells it to do. Raise the mode (`safe`, `delete_safe`, `full_access`) deliberately, per workflow, never as a blanket default.
- **Scope the tool allowlist.** `--allowedTools 'mcp__stackql__*'` limits the agent to the stackql server. Combined with `read_only`, that is the containment boundary - an injected instruction cannot reach tools you did not allow, and cannot mutate cloud state the mode forbids.
- **Pin `version` for reproducibility.** Pin both this action's tag (`@v1` floats; pin `@v1.0.0` for byte-for-byte reproducibility) and the `version:` input to a specific stackql release. Every download is sha256-verified against the release's published `.sha256`, and the MCP Registry entry `io.github.stackql/stackql-mcp` attests the per-version digests.
- **Least-privilege credentials.** Give the `auth` credentials only the cloud permissions the workflow needs, and set `permissions:` on the job to the minimum (for example `contents: read` plus `issues: write` only when the agent files issues).

## How it works

No SHAs or versions are baked into this action. At runtime it downloads the platform's `.mcpb` bundle from the stackql release proxy at `releases.stackql.io` (`releases.stackql.io/stackql/latest/...` for `latest`, otherwise `releases.stackql.io/stackql/v<version>/...`), fetches that release's matching `.sha256`, verifies the digest before extracting, and emits the `mcpServers` config. A new stackql release needs zero changes here - publish it once, point the floating `v1` tag at this action, done.

The emitted server is launched cwd-independently (`--approot ${HOME}/.stackql`, audit disabled via `--mcp.config`), because MCP hosts may run with an unwritable working directory.

## Links

- StackQL: [stackql.io](https://stackql.io)
- Documentation: [stackql.io/docs](https://stackql.io/docs)
- Provider registry and auth setup: [stackql.io/registry](https://stackql.io/registry)
- MCP Registry entry: [`io.github.stackql/stackql-mcp`](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.stackql/stackql-mcp)
- `claude-code-action`: [github.com/anthropics/claude-code-action](https://github.com/anthropics/claude-code-action)

## License

[MIT](LICENSE)
