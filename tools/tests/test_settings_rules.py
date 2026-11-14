# SPDX-License-Identifier: Apache-2.0
"""Project permission rules (.claude/settings.json): destructive and
publication commands always ask, nothing broader is allowed (audit X-01 and
I-08, decision B of 2026-11-13). The rules only add a confirmation: the
commands keep their own refusals and checks."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PWS = "python3 -m tools.pws_workspace "

# one representative invocation per destructive or publication operation
MUST_ASK = [
    "git commit -m x", "git push", "git remote add origin x", "git tag v2.1.0",
    "gh release create v2.1.0 x.zip", "gh repo create x",
    PWS + "build-distribution --target /tmp/x --force",
    PWS + "build-release --target /tmp/x",
    PWS + "upgrade --from /tmp/pkg --apply",
    PWS + "upgrade --rollback 20261113T000000Z",
    PWS + "init --language fr --force",
    PWS + "migrate --apply",
    PWS + "migrate --rollback 20261113T000000Z",
    PWS + "maintenance cleanup --execute",
    PWS + "maintenance archives-import --plan-file p.json",
    PWS + "maintenance archives-remove-source --plan-file p.json --yes",
    PWS + "license write --slug s --kind eula",
    PWS + "license set-fields --slug s --field A=b",
    PWS + "license confirm --slug s --terms-ref x",
    PWS + "pinets install 0.10.1 --yes",
    PWS + "pinets rollback --yes",
    PWS + "pinets verify --record",
    PWS + "github publish --slug s --destination d --yes",
    PWS + "github fetch --destination d",
    PWS + "github destination-remove --name d",
    PWS + "update apply --plan-file p.json --yes",
]


def _matches(rule, command):
    m = re.fullmatch(r"Bash\((.*)\)", rule)
    if not m:
        return False
    pattern = m.group(1)
    if pattern.endswith(":*"):
        prefix = pattern[:-2]
        return command == prefix or command.startswith(prefix + " ")
    return command == pattern


class TestProjectPermissionRules(unittest.TestCase):
    def setUp(self):
        self.perms = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]

    def test_every_rule_is_well_formed(self):
        for kind in ("allow", "ask", "deny"):
            for rule in self.perms.get(kind, []):
                self.assertRegex(rule, r"^Bash\([^()]+\)$", (kind, rule))
                inner = rule[5:-1]
                self.assertNotIn("*", inner[:-2] if inner.endswith(":*") else inner, (kind, rule))

    def test_destructive_and_publication_commands_ask_and_are_never_allowed(self):
        for command in MUST_ASK:
            self.assertTrue(any(_matches(r, command) for r in self.perms["ask"]), command)
            self.assertFalse(any(_matches(r, command) for r in self.perms["allow"]), command)

    def test_read_only_commands_stay_allowed(self):
        for command in (PWS + "maintenance cleanup", PWS + "doctor", PWS + "migrate --plan",
                        PWS + "tooling-status", PWS + "pinets verify", "git status"):
            self.assertTrue(any(_matches(r, command) for r in self.perms["allow"]), command)
            self.assertFalse(any(_matches(r, command) for r in self.perms["ask"]), command)


if __name__ == "__main__":
    unittest.main()
