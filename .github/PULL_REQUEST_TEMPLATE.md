## Summary

<!-- What changed and why. Feature PRs target develop. Only a Promote to production PR targets main. -->

-

## Test plan

- [ ] `./scripts/run-tests.sh` (or PR CI) is green
- [ ] PR CI runner is `tablio-docker-runner` (HEL1), not a stage deploy
- [ ] No `.env`, tokens, or Cloudflare credentials in the diff
- [ ] Does not deploy to HEL1 and does not change production DNS (unless this is a promote)

<!--
runs-on for new/changed workflows:
  PR CI / Docker: [self-hosted, linux, x64, tablio, docker]
  no Docker:      [self-hosted, linux, x64, tablio, default]
  stage deploy:   [self-hosted, stage]   # WSL only
PostGIS in CI: publish 55432:5432 (HEL1 already uses 5432).
-->
