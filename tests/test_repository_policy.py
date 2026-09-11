"""Local contracts for reviewed policy templates, not live API/enforcement tests."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RepositoryPolicy(unittest.TestCase):
    def setUp(self):
        self.rules = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in (ROOT / ".github/rulesets").glob("*.json")
        }

    def test_definitions_are_complete_unique_and_inert(self):
        self.assertEqual(set(self.rules), {
            "default-integrity.json", "upstream-integrity.json", "main-pr.json",
            "main-ci.json", "main-merge-authority.json",
        })
        self.assertEqual(len({rule["name"] for rule in self.rules.values()}), len(self.rules))
        for rule in self.rules.values():
            self.assertEqual(set(rule), {"name", "target", "enforcement", "bypass_actors", "conditions", "rules"})
            self.assertEqual(rule["target"], "branch")
            self.assertEqual(rule["enforcement"], "disabled")
            self.assertEqual(set(rule["conditions"]), {"ref_name"})
            self.assertEqual(rule["conditions"]["ref_name"]["exclude"], [])

    def test_integrity_has_no_bypass_or_update_restriction(self):
        for filename in ("default-integrity.json", "upstream-integrity.json"):
            rule = self.rules[filename]
            self.assertEqual(rule["bypass_actors"], [])
            self.assertEqual(rule["rules"], [{"type": "deletion"}, {"type": "non_fast_forward"}])
        self.assertEqual(self.rules["upstream-integrity.json"]["conditions"]["ref_name"]["include"],
                         ["refs/heads/upstream/*", "refs/heads/upstream/**/*"])
        for filename, rule in self.rules.items():
            if filename != "upstream-integrity.json":
                self.assertEqual(rule["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])

    def test_operator_bypass_is_confined_to_the_update_gate(self):
        authority = self.rules["main-merge-authority.json"]
        self.assertEqual(authority["bypass_actors"], [
            {"actor_type": "User", "actor_id": 118467860, "bypass_mode": "always"}
        ])
        self.assertEqual(authority["rules"], [
            {"type": "update", "parameters": {"update_allows_fetch_and_merge": False}}
        ])
        for filename, rule in self.rules.items():
            if filename != "main-merge-authority.json":
                self.assertEqual(rule["bypass_actors"], [])

    def test_pr_and_ci_gate_preconditions_remain_explicit(self):
        pr = self.rules["main-pr.json"]["rules"][0]
        self.assertEqual(pr["type"], "pull_request")
        self.assertEqual(pr["parameters"]["required_approving_review_count"], 0)
        self.assertTrue(pr["parameters"]["required_review_thread_resolution"])
        ci = self.rules["main-ci.json"]["rules"][0]
        self.assertEqual(ci["type"], "required_status_checks")
        self.assertTrue(ci["parameters"]["strict_required_status_checks_policy"])
        self.assertEqual(ci["parameters"]["required_status_checks"], [
            {"context": "Documentation integrity", "integration_id": None}
        ])
        # Null is deliberate only because this template is disabled and unqualified.
        self.assertEqual(self.rules["main-ci.json"]["enforcement"], "disabled")


if __name__ == "__main__":
    unittest.main()
