# SPDX-License-Identifier: Apache-2.0
"""Project permission rules (.claude/settings.json): the main destructive and
publication commands ask, nothing broader is allowed (audit X-01 and I-08,
decision B of 2026-11-13). Since 2.1.2 (holder's decision of 2026-11-14),
routine local acts — local commits, local builds, update searches and
downloads without application — carry no PWS ask rule (Claude Code decides as
usual) and Git/GitHub reading is allowed. The rules only add a confirmation:
the commands keep their own refusals and checks. This file checks the rules
statically; it does not observe Claude Code."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PWS = "python3 -m tools.pws_workspace "

# one representative invocation per destructive or publication operation
MUST_ASK = [
    "git push", "git push origin v2.1.2", "git remote add origin x", "git remote set-url origin x",
    "git remote remove origin", "git remote rm origin", "git remote rename origin up",
    "git tag -d v2.1.0", "git tag --delete v2.1.0", "git tag -f v2.1.0", "git tag --force v2.1.0",
    "gh release create v2.1.0 x.zip", "gh release edit v2.1.0", "gh release upload v2.1.0 x.zip",
    "gh release delete v2.1.0", "gh release delete-asset v2.1.0 x.zip", "gh repo create x",
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
    PWS + "update guide --stage apply --plan-file p.json --yes",
    PWS + "pinets guide --stage apply --plan-file p.json --yes",
]


# routine local acts and readings: no PWS ask rule (2.1.2) — Claude Code decides as usual
MUST_NOT_ASK = [
    "git commit -m x", "git commit -q -F msg.txt", "git tag", "git remote", "git remote -v",
    "git remote get-url origin", "gh release view v2.1.1", "gh release list",
    PWS + "build-distribution --target /tmp/x --force",
    PWS + "build-release --target /tmp/x",
    PWS + "update check", PWS + "update fetch --tag v2.1.1",
    PWS + "pinets check-update",
    # guided paths (2.2.0): state, search and preparation (download outside the installation, plan file)
    PWS + "update guide --stage state", PWS + "update guide --stage search", PWS + "update guide --stage prepare",
    PWS + "pinets guide --stage state", PWS + "pinets guide --stage search",
    PWS + "pinets guide --stage prepare 0.13.1",
]
# readings allowed explicitly (no prompt from the project rules)
MUST_ALLOW = ["git remote", "git remote -v", "git remote get-url origin", "git tag",
              "gh release view v2.1.1 --repo o/r", "gh release list", "gh release view"]


def _matches(rule, command):
    """Static model of the documented matching: `Bash(cmd)` exact, `Bash(cmd:*)`
    and `Bash(cmd *)` = the command itself or the command followed by arguments.
    Command text only, like Claude Code: other spellings of the same act
    (`git -C dir remote add`, `gh -R o/r release create`) are not matched."""
    m = re.fullmatch(r"Bash\((.*)\)", rule)
    if not m:
        return False
    pattern = m.group(1)
    for suffix in (":*", " *"):
        if pattern.endswith(suffix):
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
                core = inner[:-2] if inner.endswith((":*", " *")) else inner
                self.assertNotIn("*", core, (kind, rule))   # a wildcard only at the end

    def test_destructive_and_publication_commands_ask_and_are_never_allowed(self):
        for command in MUST_ASK:
            self.assertTrue(any(_matches(r, command) for r in self.perms["ask"]), command)
            self.assertFalse(any(_matches(r, command) for r in self.perms["allow"]), command)

    def test_routine_local_acts_have_no_ask_rule_and_no_broad_allow(self):
        for command in MUST_NOT_ASK:
            self.assertFalse(any(_matches(r, command) for r in self.perms["ask"]), command)
        for command in MUST_ALLOW:
            self.assertTrue(any(_matches(r, command) for r in self.perms["allow"]), command)
        # no general authorization was added in their place
        for broad in ("Bash", "Bash(*)", "Bash(git:*)", "Bash(git *)", "Bash(gh:*)", "Bash(gh *)",
                      "Bash(python3:*)", "Bash(python3 *)", "Bash(node:*)", "Bash(npm:*)",
                      "Bash(python3 -m tools.pws_workspace:*)", "Bash(python3 -m tools.pws_workspace *)",
                      "Bash(git commit:*)", "Bash(git tag:*)", "Bash(gh release:*)", "Bash(git remote:*)"):
            self.assertNotIn(broad, self.perms["allow"], broad)
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("defaultMode", self.perms)
        self.assertNotIn("autoMode", settings)
        self.assertEqual(sorted(settings["hooks"]), ["SessionStart", "Stop"])
        self.assertEqual(sorted(self.perms["deny"]), sorted([
            "Bash(gh repo delete:*)", "Bash(gh api:*)", "Bash(gh secret:*)", "Bash(gh auth token:*)",
            "Bash(git push --force:*)", "Bash(git push -f:*)"]))

    def test_read_only_commands_stay_allowed(self):
        for command in (PWS + "maintenance cleanup", PWS + "doctor", PWS + "migrate --plan",
                        PWS + "tooling-status", PWS + "pinets verify", "git status"):
            self.assertTrue(any(_matches(r, command) for r in self.perms["allow"]), command)
            self.assertFalse(any(_matches(r, command) for r in self.perms["ask"]), command)


if __name__ == "__main__":
    unittest.main()
