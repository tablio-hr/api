import os
import subprocess
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / "scripts"


class DnsScriptAllowlistTests(SimpleTestCase):
    def _run(self, script: str, extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(extra_env)
        return subprocess.run(
            ["bash", str(SCRIPTS / script)],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_production_rejects_stage_name(self):
        result = self._run(
            "cloudflare_dns_upsert.sh",
            {
                "CF_DNS_TOKEN_PRODUCTION": "test-token",
                "TABLIO_DNS_NAMES": "admin-stage.tablio.hr",
                "TABLIO_DRY_RUN": "1",
            },
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("allowlist", result.stderr.lower() + result.stdout.lower())

    def test_stage_rejects_production_name(self):
        result = self._run(
            "cloudflare_tunnel_upsert.sh",
            {
                "CF_DNS_TOKEN_STAGE": "test-token",
                "CLOUDFLARE_TUNNEL_ID": "00000000-0000-0000-0000-000000000000",
                "TABLIO_DNS_NAMES": "admin.tablio.hr",
                "TABLIO_DRY_RUN": "1",
            },
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("allowlist", result.stderr.lower() + result.stdout.lower())
