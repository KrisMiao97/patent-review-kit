"""Portable data/component regressions. Run from the Skill root with unittest."""
import base64
import copy
import json
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import render_review as r


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.ids, self.links, self.tags = [], [], []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            self.links.append(attrs["href"][1:])


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "examples/template-input.json").read_text(encoding="utf8"))
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name)

    def render(self, data=None):
        return r.render(r.validate(data or self.data), self.path)

    def test_fragments_and_unique_ids(self):
        doc = Document(self.render())
        self.assertEqual(len(doc.ids), len(set(doc.ids)))
        self.assertFalse(set(doc.links) - set(doc.ids))

    def test_zero_issue_sections_have_no_filter_links(self):
        doc = Document(self.render())
        actual = {a["data-filter-section"] for _, a in doc.tags if "data-filter-section" in a}
        self.assertEqual(actual, {"description"})
        self.assertIn('data-coverage-section="abstract"', self.render())

    def test_counts_follow_relationships_in_both_outputs(self):
        self.data["figures"] = [dict(figure="图 8", page="无页码示例", visual_status="unread", observation="未核读", issues=["EX-01"])]
        output = self.render()
        self.assertEqual(output.count("1 条权项对照 · 1 条附图记录"), 2)
        self.assertNotIn('id="related-EX-02"', output)
        self.data["evidence"][0]["issues"] = ["EX-02"]
        output = self.render()
        self.assertEqual(output.count("0 条权项对照 · 1 条附图记录"), 2)
        self.assertEqual(output.count("1 条权项对照 · 0 条附图记录"), 2)

    def test_summary_does_not_repeat_technical_points(self):
        self.data["claim_index"][1]["summary"] = "仅供此路径显示的独有技术要点。"
        source = self.render()
        self.assertEqual(source.count("仅供此路径显示的独有技术要点。"), 1)
        self.assertIn('aria-label="EX-01 开启阈值的等值动作待确认"', source)

    def test_legal_sources_no_empty_list(self):
        source = self.render()
        self.assertNotIn("<ul></ul>", source)
        self.assertIn('<details class="legal"', source)
        self.assertLess(source.index('id="edit-EX-01"'), source.index('id="law-EX-01"'))

    def test_empty_report_and_optional_sections(self):
        for key in ("issues", "actions", "evidence", "figures", "search", "conditions", "claim_index", "technology"):
            self.data[key] = []
        source = self.render()
        doc = Document(source)
        self.assertNotIn("mechanism", doc.ids)
        self.assertNotIn("conditions", doc.ids)
        self.assertNotIn("claim-overview", doc.ids)
        self.assertFalse(set(doc.links) - set(doc.ids))
        self.assertIn("本轮未单列审核意见", source)

    def test_mixed_status_filter(self):
        source = self.render()
        self.assertIn('<option value="resolved">已解决</option>', source)
        self.assertNotIn('<option value="rejected">', source)
        self.assertIn('<label>处理进度<select', source)

    def test_single_status_is_explained(self):
        self.data["issues"][1]["status"] = "pending"
        source = self.render()
        self.assertIn('处理进度均为“待确认”', source)
        self.assertIn('<label hidden>处理进度<select', source)

    def test_safe_text_and_plain_originals(self):
        quote = '<script>alert("x")</script> $title A & B 权 123'
        self.data["issues"][0]["originals"][0]["quote"] = quote
        source = self.render()
        self.assertNotIn('<script>alert', source)
        self.assertIn(r.e(quote), source)
        self.assertIn('$title', source)

    def test_invalid_relations(self):
        self.data["conditions"][0]["issues"] = ["UNDEFINED"]
        with self.assertRaises(ValueError):
            self.render()

    def test_reference_identity_and_link_validation(self):
        self.data["references"] = [dict(id="D1", title="虚构文献身份", note="示例位置与边界", url="https://example.com/document")]
        self.data["issues"][0]["reference_ids"] = ["D1"]
        source = self.render()
        self.assertIn('href="#ref-D1"', source)
        self.data["references"][0]["url"] = "javascript:alert(1)"
        with self.assertRaises(ValueError):
            self.render()

    def test_focus_requires_explicit_common_scope(self):
        self.data["search"][0]["focus"] = "重点"
        with self.assertRaises(ValueError):
            self.render()
        self.data["search_common"] = "共同范围未执行"
        self.assertIn("本项检索重点", self.render())

    def test_image_embedding_and_path_boundary(self):
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j5c8AAAAASUVORK5CYII=')
        (self.path / "source.png").write_bytes(png)
        self.data["drawing_pages"] = [dict(file="source.png", label="示例图", source="测试文件")]
        self.assertIn("data:image/png;base64," + base64.b64encode(png).decode(), self.render())
        self.data["drawing_pages"][0]["file"] = "../source.png"
        with self.assertRaises(ValueError):
            self.render()

    def test_invalid_image_and_missing_file(self):
        self.data["drawing_pages"] = [dict(file="source.png", label="示例图", source="测试")]
        with self.assertRaises(OSError):
            self.render()
        (self.path / "source.png").write_text("<svg></svg>")
        with self.assertRaises(ValueError):
            self.render()

    def test_legacy_versions_keep_phase_warning(self):
        for version in (1, 2):
            data = copy.deepcopy(self.data)
            data["schema_version"] = version
            if version == 1:
                for issue in data["issues"]:
                    issue.update(location="旧版示例位置", reference_fix="旧版候选改法")
            source = self.render(data)
            self.assertIn("适用阶段待补核", source)
            self.assertIn('id="issue-EX-01"', source)

    def test_unknown_phase_rejects_current_draft_edits(self):
        self.data["phase"] = "unknown"
        with self.assertRaises(ValueError):
            self.render()

    def test_delivery_is_separate_from_review(self):
        source = self.render()
        self.assertIn("文件交付", source)
        self.assertIn("人工复核", source)
        self.assertIn("未作实际案件复核", source)

    def test_duplicate_metadata_and_ids(self):
        self.data["meta"].append(dict(label="人工复核", text="重名"))
        with self.assertRaises(ValueError):
            self.render()
        self.data["meta"].pop()
        self.data["issues"][1]["id"] = "EX-01"
        with self.assertRaises(ValueError):
            self.render()


if __name__ == "__main__":
    unittest.main()
