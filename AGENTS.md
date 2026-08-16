# Tablio API — agent instructions

Repo: [tablio-hr/api](https://github.com/tablio-hr/api).  
Boundaries: [ADR 0001](https://github.com/tablio-hr/docs/blob/develop/architecture/adr/0001-platform-deployment-and-tenancy-boundary.md).  
PRs start only after the authorizing implementation plan is merged in `tablio-hr/docs`.

## Pull requests

- Feature PRs target **`develop`**. Do not open feature PRs against `main`.
- The only `develop` → `main` path is a **Promote to production** PR.
- After merge, delete the feature branch locally and on `origin`. Never delete `develop` or `main`.
- Use `.github/PULL_REQUEST_TEMPLATE.md`. Fill Summary and Test plan.
- Do not commit `.env`, tokens, or Cloudflare credentials.

```text
feature PR → CI → develop (WSL stage) → Promote to production PR → main (HEL1)
```

## CI runners

Org `tablio-hr` self-hosted runners on **dedicated-hel1**, group **Dedicated**.
They are already registered — do not add **New runner**.

| Job | `runs-on` |
|-----|-----------|
| PR CI / Docker / `services:` | `[self-hosted, linux, x64, tablio, docker]` |
| lint / tests without Docker | `[self-hosted, linux, x64, tablio, default]` |

CI on dedicated-hel1 is allowed. Stage **deploy** is manual on WSL
(`./scripts/deploy-stage.sh`). There is no GitHub Actions stage runner.
Never put a `stage` label on the HEL1 runners.

HEL1 already uses `127.0.0.1:5432`. In `.github/workflows/pr-ci.yml` publish
PostGIS as `55432:5432` and set `DB_PORT: "55432"`. Do not map `5432:5432`.

CI must not run `scripts/deploy-stage.sh`, `scripts/deploy-production.sh`, or
compose against `/opt/stacks/tablio.hr`.

Runners UI: https://github.com/organizations/tablio-hr/settings/actions/runners  
`tablio-runner` (`default`) and `tablio-docker-runner` (`docker`) must stay Idle
in group Dedicated, with **allow public repositories** on.

## Local tests

```bash
./scripts/run-tests.sh
```

PostGIS only (`config.settings.test`). Not SQLite. Not the live `DB_NAME`.
