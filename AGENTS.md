# Tablio API — agent instructions

Repo: [tablio-hr/api](https://github.com/tablio-hr/api).  
Boundaries: [ADR 0001](https://github.com/tablio-hr/docs/blob/develop/architecture/adr/0001-platform-deployment-and-tenancy-boundary.md).  
API work starts only after the authorizing implementation plan is merged in `tablio-hr/docs`.

## Release path

```text
WSL develop (direct commit) → manual stage deploy → stage smoke
  → Promote to production PR → CI on HEL1 → main → production deploy
```

- Land feature work and bugfixes on **`develop`** with a direct commit. Do not
  open a feature PR.
- The only PR is **Promote to production** (`develop` → `main`). That PR is
  the CI gate. Do not commit to `main`.
- After a promote merge, delete the promote branch (local + remote). Never
  delete `develop` or `main`.
- `develop` never deploys to HEL1. `main` never changes stage.
- Do not commit `.env`, tokens, or Cloudflare credentials.

## Stage

Manual on WSL: `./scripts/deploy-stage.sh`. No GitHub Actions stage job and
no `stage` runner. Stage can be red until someone notices; run local tests
before you commit API changes.

## CI

`pr-ci.yml` runs on **pull_request** (the promote PR), not on push to
`develop`. HEL1 runners, group **Dedicated**. Already registered — do not
add **New runner**. Never put a `stage` label on them.

| Job | `runs-on` |
|-----|-----------|
| PR CI / Docker / `services:` | `[self-hosted, linux, x64, tablio, docker]` |
| lint / tests without Docker | `[self-hosted, linux, x64, tablio, default]` |

HEL1 already uses `127.0.0.1:5432`. Publish job PostGIS as `55432:5432` and
set `DB_PORT: "55432"`.

CI must not run `scripts/deploy-stage.sh`, `scripts/deploy-production.sh`, or
compose against `/opt/stacks/tablio.hr`.

Runners UI: https://github.com/organizations/tablio-hr/settings/actions/runners

## Local tests

```bash
./scripts/run-tests.sh
```

PostGIS only (`config.settings.test`). Not SQLite. Not the live `DB_NAME`.
