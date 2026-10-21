"""Standing version pins and literal historical preview behavior contracts."""
from collections import Counter
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aesop_lab.content import load_pack
from aesop_lab import foreman


class VersionRegistryTests(unittest.TestCase):
    def test_registry_covers_pack_files_and_unique_assignment_versions(self):
        rows = foreman.VERSION_REGISTRY
        packs = tuple(load_pack(path) for path in
                      (foreman.ROOT / "content/packs/python-functions-recursion").glob("*.json"))
        expected = Counter(concept.content_version for pack in packs
                           for concept in pack.concepts[:1])
        self.assertEqual(Counter(row.content_version for row in rows), expected)
        self.assertEqual(Counter(row.pack_path for row in rows), Counter(
            (foreman.ROOT / "content/packs/python-functions-recursion").glob("*.json")))
        assignments = Counter(row.assignment_protocol_version for row in rows
                              if row.assignment_protocol_version is not None)
        self.assertEqual(assignments, Counter({"v1": 1, "v2": 1, "v3": 1, "v4": 1,
                                               "v5": 1, "v6": 1, "v7": 1, "v8": 1}))
        for row in rows:
            with self.subTest(version=row.content_version):
                self.assertEqual({c.content_version for c in load_pack(row.pack_path).concepts},
                                 {row.content_version})
                if row.comparison:
                    self.assertEqual(row.comparison.load()[0].version, row.assignment_protocol_version)

    def test_standing_current_pack_content_protocol_and_seed_pin(self):
        from aesop_lab.experiment.descriptive_v8 import DESCRIPTIVE_V8
        row = foreman.VERSION_REGISTRY[-1]
        pack = load_pack(foreman.CURRENT_PACK_PATH)
        self.assertEqual(pack.pack_version, "m2-draft.11")
        self.assertEqual({c.content_version for c in pack.concepts}, {"v11"})
        self.assertEqual(row.content_version, "v11")
        self.assertEqual(row.pack_path.name, "pack-m2-draft.11.json")
        self.assertEqual(row.pack_path, foreman.CURRENT_PACK_PATH)
        self.assertEqual(row.assignment_protocol_version, "v8")
        self.assertEqual(row.comparison.module, "aesop_lab.experiment.descriptive_v8")
        self.assertEqual(row.comparison.protocol_name, "DESCRIPTIVE_V8")
        self.assertIs(row.comparison.load()[0], DESCRIPTIVE_V8)
        self.assertEqual(DESCRIPTIVE_V8.version, "v8")
        self.assertEqual(DESCRIPTIVE_V8.seed, 20261021)

    def test_literal_master_behavior_for_every_version(self):
        # Baseline 4c120ff: policy, plain language, target, descriptive signature,
        # protocol module, constant, and protocol version (no inferred expectations).
        expected = {
            "v1": ("pilot-v1", False, False, False, None, None, None),
            "v2": ("pilot-v1", False, False, False, None, None, None),
            "v3": ("pilot-v2", False, False, False, None, None, None),
            "v4": ("pilot-v2", False, False, False, "aesop_lab.experiment", "PROTOCOL", "v1"),
            "v5": ("pilot-v4", False, True, True, "aesop_lab.experiment.descriptive_v2", "DESCRIPTIVE_V2", "v2"),
            "v6": ("pilot-v4", False, True, True, "aesop_lab.experiment.descriptive_v3", "DESCRIPTIVE_V3", "v3"),
            "v7": ("pilot-v4", False, True, True, "aesop_lab.experiment.descriptive_v4", "DESCRIPTIVE_V4", "v4"),
            "v8": ("pilot-v4", False, True, True, "aesop_lab.experiment.descriptive_v5", "DESCRIPTIVE_V5", "v5"),
            "v9": ("pilot-v4", False, True, True, "aesop_lab.experiment.descriptive_v6", "DESCRIPTIVE_V6", "v6"),
            "v10": ("pilot-v5", True, True, True, "aesop_lab.experiment.descriptive_v7", "DESCRIPTIVE_V7", "v7"),
            "v11": ("pilot-v5", True, True, True, "aesop_lab.experiment.descriptive_v8", "DESCRIPTIVE_V8", "v8"),
        }
        self.assertEqual({r.content_version for r in foreman.VERSION_REGISTRY}, set(expected))
        with TemporaryDirectory() as temp:
            for row in foreman.VERSION_REGISTRY:
                with self.subTest(version=row.content_version):
                    policy, plain, target, descriptive, module, constant, protocol_version = expected[row.content_version]
                    self.assertEqual((row.policy_version, row.plain_language,
                                      row.report_study_target, row.descriptive_analysis),
                                     (policy, plain, target, descriptive))
                    preview = foreman.Preview(Path(temp) / (row.content_version + ".db"))
                    try:
                        preview._activate_pack(row.pack_path)
                        self.assertEqual({s.policy_version for s in preview.services.values()}, {policy})
                        cid = preview.pack.learning_order()[0]
                        method = preview._method_for(cid)
                        findings = preview.experiment_findings()
                        if module is None:
                            self.assertIsNone(row.comparison)
                            self.assertIsNone(method)
                            self.assertEqual(findings, {"status": "insufficient_evidence", "reason": "This content version predates the fixed comparison."})
                        else:
                            self.assertEqual((row.comparison.module, row.comparison.protocol_name), (module, constant))
                            protocol = getattr(import_module(module), constant)
                            self.assertIs(row.comparison.load()[0], protocol)
                            self.assertEqual(method["protocolId"], "text-vs-labeled-diagram")
                            self.assertEqual(method["protocolVersion"], protocol_version)
                            self.assertEqual("studyTargetMinutes" in method, target)
                            self.assertEqual(findings["protocol"]["version"], protocol_version)
                    finally:
                        preview.store.close()
