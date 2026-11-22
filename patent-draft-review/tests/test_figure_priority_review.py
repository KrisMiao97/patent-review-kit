import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from render_review import render, validate


class FigurePriorityReviewTests(unittest.TestCase):
    def inputs(self):
        data = json.loads((ROOT / "examples/template-input.json").read_text(encoding="utf-8"))
        data["schema_version"] = 5
        for row in data["coverage"]:
            if row["section"] == "drawings":
                row.update(status="reviewed", note="已查看并核对两个图")
        data["gaps"] = [gap for gap in data["gaps"] if gap["section"] != "drawings"]
        data["issues"][0]["impact"] = {"claim": "material", "claim_target": "权 1",
                                        "effect": "none", "reason": "争议会改变触发条件的读法。"}
        data["issues"][1].update(priority="medium", impact={"claim": "local", "effect": "none",
                                                             "reason": "局部疑似抄错编号。"})
        data["figures"] = [{"figure": f"图 {number}", "page": "8", "observation": "实看",
                             "visual_status": "seen", "issues": ["EX-02"]} for number in (1, 2)]
        data["figure_audit"] = {"status": "checked", "legend": [
            {"mark": "11", "name": "按键", "source": "[0021]"},
            {"mark": "111", "name": "稳固部", "source": "[0021]"},
        ], "views": [{"figure": "图 1", "page": "8", "description_ref": "[0016]", "status": "checked", "marks": [
            {"mark": "111", "target": "按键整体括引", "legend_mark": "11", "status": "suspect", "issue": "EX-02", "note": "与另一视图的编号不同。"},
            {"mark": "111", "target": "引向稳固部", "legend_mark": "111", "status": "match"},
        ]}, {"figure": "图 2", "page": "8", "description_ref": "[0017]", "status": "checked", "marks": [
            {"mark": "11", "target": "按键整体括引", "legend_mark": "11", "status": "match"},
        ]}]}
        return data

    def test_same_number_with_distinct_targets_is_reported(self):
        page = render(validate(self.inputs()), ROOT / "examples")
        self.assertIn("逐图编号与说明书核对", page)
        self.assertIn("111 · 按键整体括引", page)
        self.assertIn("111 · 引向稳固部", page)
        self.assertIn("优先级依据", page)

    def test_omitted_view_and_unlinked_discrepancy_are_rejected(self):
        data = self.inputs()
        data["figure_audit"]["views"].pop()
        with self.assertRaisesRegex(ValueError, "逐一登记"):
            validate(data)
        data = self.inputs()
        del data["figure_audit"]["views"][0]["marks"][0]["issue"]
        with self.assertRaisesRegex(ValueError, "须关联一条意见"):
            validate(data)

    def test_local_issue_on_independent_claim_can_be_medium(self):
        data = self.inputs()
        first = data["issues"][0]
        first["priority"] = "medium"
        first["impact"] = {"claim": "none", "effect": "local", "reason": "幅度有待测量，已披露基本机制。"}
        data["causal_review"]["chains"][0]["critical"] = False
        validate(data)
        first["priority"] = "high"
        with self.assertRaisesRegex(ValueError, "优先级与权项、效果影响不符"):
            validate(data)

    def test_unread_figure_cannot_be_marked_complete(self):
        data = self.inputs()
        data["figure_audit"]["views"][0].update(status="unread", marks=[], reason="尚未看图")
        with self.assertRaisesRegex(ValueError, "缺图或未看清"):
            validate(data)
