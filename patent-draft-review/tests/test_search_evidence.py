"""Exercise the reviewed-evidence gate through validation, rendering and the CLI."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from render_review import render, validate


class SearchEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "examples/search-evidence-input.json").read_text(encoding="utf-8"))
        self.search = self.data["search"][0]

    def complete_single_document(self):
        starting = self.search["comparisons"][0]
        starting["features"][2].update(
            status="disclosed", location="D1 [0012]", quote="同一方案控制器低于40 lx开灯。",
            reason="同一方案公开 C，与 A、B 共同使用。")
        starting["combination"].update(status="complete", location="D1 [0010]至[0012]",
                                        reason="同一方案共同公开 A、B、C 及配合条件。")
        self.search["novelty"].update(result="complete_combination_found", basis="D1 单篇完整组合。")
        self.search["inventiveness"].update(difference_ids=[], combination={
            "status": "not_needed", "reason": "起点已完整公开，无需另行组合。", "evidence": []})

    def test_abc_complete_evidence_passes_and_is_visible(self):
        page = render(validate(self.data), ROOT / "examples")
        for text in ("D1 [0010]", "D2 [0021]至[0022]", "区别特征 C", "逐特征现有技术证据"):
            self.assertIn(text, page)
        self.complete_single_document()
        self.assertIn("已发现单篇完整组合", render(validate(self.data), ROOT / "examples"))

    def test_each_feature_needs_location_and_quote(self):
        for index in range(3):
            for field in ("location", "quote"):
                with self.subTest(feature=index, field=field):
                    data = copy.deepcopy(self.data)
                    del data["search"][0]["comparisons"][0]["features"][index][field]
                    with self.assertRaisesRegex(ValueError, field):
                        validate(data)

    def test_non_disclosure_requires_scope_and_reason(self):
        for field in ("checked_scope", "reason"):
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                data["search"][0]["comparisons"][0]["features"][2][field] = " "
                with self.assertRaisesRegex(ValueError, field):
                    validate(data)

    def test_missing_duplicate_and_unknown_feature_are_rejected(self):
        for mode in ("missing", "duplicate", "unknown"):
            with self.subTest(mode=mode):
                data = copy.deepcopy(self.data)
                rows = data["search"][0]["comparisons"][0]["features"]
                if mode == "missing":
                    rows.pop()
                elif mode == "duplicate":
                    rows.append(copy.deepcopy(rows[0]))
                else:
                    rows[0]["feature_id"] = "UNKNOWN"
                with self.assertRaises(ValueError):
                    validate(data)

    def test_two_documents_cannot_be_pooled_into_novelty(self):
        self.search["novelty"]["result"] = "complete_combination_found"
        with self.assertRaisesRegex(ValueError, "单篇文献"):
            validate(self.data)
        self.search["comparisons"][0]["combination"]["status"] = "complete"
        with self.assertRaisesRegex(ValueError, "本单篇方案"):
            validate(self.data)

    def test_separate_schemes_in_one_document_are_not_pooled(self):
        self.search["comparisons"][1]["reference_id"] = "D1"
        self.search["comparisons"][1]["scheme"] = "互不组合的实施方案2"
        validate(self.data)
        self.search["novelty"]["result"] = "complete_combination_found"
        with self.assertRaisesRegex(ValueError, "单篇文献"):
            validate(self.data)

    def test_complete_combination_needs_location(self):
        self.complete_single_document()
        del self.search["comparisons"][0]["combination"]["location"]
        with self.assertRaisesRegex(ValueError, "combination.location"):
            validate(self.data)

    def test_unknown_reference_is_rejected(self):
        self.search["comparisons"][0]["reference_id"] = "D404"
        with self.assertRaisesRegex(ValueError, "reference_id"):
            validate(self.data)

    def test_unverified_is_allowed_only_for_partial_judgment(self):
        self.search["comparisons"][0]["features"][2]["status"] = "unverified"
        with self.assertRaisesRegex(ValueError, "不能标已核查"):
            validate(self.data)
        for name in ("novelty", "inventiveness"):
            self.search[name]["status"] = "partial"
        for row in self.data["coverage"]:
            if row["section"] == "search":
                row["status"] = "partial"
        self.data["gaps"] = [{"section": "search", "note": "C 尚待回原件核实。"}]
        self.assertIn("待核", render(validate(self.data), ROOT / "examples"))

    def test_difference_list_must_match_starting_document(self):
        self.search["inventiveness"]["difference_ids"] = []
        with self.assertRaisesRegex(ValueError, "difference_ids"):
            validate(self.data)

    def test_combination_evidence_missing_and_incomplete_are_rejected(self):
        combination = self.search["inventiveness"]["combination"]
        for field in ("location", "quote", "reason", "feature_ids"):
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                del data["search"][0]["inventiveness"]["combination"]["evidence"][0][field]
                with self.assertRaises(ValueError):
                    validate(data)
        combination["evidence"] = []
        with self.assertRaisesRegex(ValueError, "覆盖全部区别特征"):
            validate(self.data)

    def test_combination_cannot_cite_an_undisclosed_feature(self):
        self.search["inventiveness"]["combination"]["evidence"][0]["comparison_id"] = "D1-S1"
        with self.assertRaisesRegex(ValueError, "所指特征须有公开证据"):
            validate(self.data)

    def test_lack_of_combination_basis_records_scope(self):
        combination = self.search["inventiveness"]["combination"]
        combination.update(status="unsupported", evidence=[], reason="本轮未找到适用于该工况的结合指引。")
        with self.assertRaisesRegex(ValueError, "checked_scope"):
            validate(self.data)
        combination["checked_scope"] = "已核读 D1、D2 全部方案及迁移条件。"
        validate(self.data)

    def test_legacy_reviewed_labels_cannot_bypass_gate(self):
        for version in (1, 2, 3, 4, 5):
            with self.subTest(version=version):
                data = copy.deepcopy(self.data)
                data["schema_version"] = version
                if version == 1:
                    for issue in data["issues"]:
                        issue.update(location="虚构原文", reference_fix="虚构改法")
                del data["search"][0]["features"]
                del data["search"][0]["comparisons"]
                with self.assertRaisesRegex(ValueError, "features"):
                    validate(data)

    def test_cli_rejects_missing_evidence_without_creating_output(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source, output = folder / "input.json", folder / "output.html"
            source.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            command = [sys.executable, "-B", str(ROOT / "scripts/render_review.py"), str(source), "--output", str(output)]
            good = subprocess.run(command, capture_output=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertTrue(output.is_file())
            output.unlink()
            del self.search["comparisons"][0]["features"][2]["checked_scope"]
            source.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            bad = subprocess.run(command, capture_output=True)
            self.assertEqual(bad.returncode, 2)
            self.assertFalse(output.exists())

    def test_evidence_text_is_escaped(self):
        self.search["comparisons"][0]["features"][0]["quote"] = '<script>alert("evidence")</script>'
        page = render(validate(self.data), ROOT / "examples")
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn('<script>alert("evidence")</script>', page)


if __name__ == "__main__":
    unittest.main()
