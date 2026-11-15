"""Exercise the actual Word export path when python-docx is available."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


@unittest.skipUnless(importlib.util.find_spec('docx'), 'python-docx is required for Word export tests')
class WordExportTests(unittest.TestCase):
    def setUp(self):
        from docx import Document
        self.Document = Document
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.source = self.directory / 'source.docx'
        self.plan = self.directory / 'plan.json'
        self.annotated = self.directory / 'annotated.docx'
        self.clean = self.directory / 'clean.docx'
        self.original = '1. 一种种苗箱，包括箱体及控制器。'
        document = Document()
        document.add_heading('权利要求书', level=1)
        document.add_paragraph(self.original)
        document.add_paragraph('3. 根据权利要求1所述的种苗箱，其还包括箱门。')
        self.original_text = [paragraph.text for paragraph in document.paragraphs]
        document.save(self.source)
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def export(self, paragraphs):
        from export_review import write_pair
        plan = {'source_sha256':self.digest, 'issues':[{
            'id':'D-01', 'problem':'新增候选2。', 'reference_fix':'采用两段候选文字。', 'status':'adopted',
            'anchor':{'paragraph':2,'quote':self.original},
            'edits':[{'paragraph':2,'before':self.original,'insert_after':paragraphs}]}]}
        self.plan.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
        return write_pair(self.source, self.plan, self.annotated, self.clean)

    def test_multiline_element_reports_paragraph_split_and_leaves_no_outputs(self):
        with self.assertRaisesRegex(ValueError, r'insert_after\[0\].*按 Word 段落拆'):
            self.export(['2. 根据权利要求1所述的种苗箱。\r\n所述箱体设有照度传感器。'])
        self.assertFalse(self.clean.exists())
        self.assertFalse(self.annotated.exists())
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.digest)

    def test_split_paragraphs_preserve_order_and_match_in_both_word_files(self):
        paragraphs = ['2. 根据权利要求1所述的种苗箱，其特征在于：', '所述箱体设有照度传感器。']
        self.assertEqual(self.export(paragraphs), (1, 1))
        expected = self.original_text[:2] + paragraphs + self.original_text[2:]
        clean, annotated = self.Document(self.clean), self.Document(self.annotated)
        self.assertEqual([p.text for p in clean.paragraphs], expected)
        self.assertEqual([p.text for p in annotated.paragraphs], expected)
        self.assertEqual(len(clean.comments), 0)
        self.assertEqual(len(annotated.comments), 1)
