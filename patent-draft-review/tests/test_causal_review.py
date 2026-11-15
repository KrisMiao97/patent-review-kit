"""Structural gates for causal review. Textual causal validity still needs review."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import render_review as r
from test_render_review import Document


class CausalReviewTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'examples/template-input.json').read_text(encoding='utf8'))
        self.review = self.data['causal_review']
        self.chain = self.review['chains'][0]

    def render(self, data=None):
        with tempfile.TemporaryDirectory() as folder:
            return r.render(r.validate(data or self.data), Path(folder))

    def test_new_report_requires_causal_review(self):
        self.data.pop('causal_review')
        with self.assertRaisesRegex(ValueError, 'causal_review'):
            r.validate(self.data)

    def test_all_three_inventories_are_required(self):
        for field in ('targets', 'problems', 'chains'):
            data = copy.deepcopy(self.data)
            data['causal_review'][field] = []
            with self.subTest(field=field), self.assertRaises(ValueError):
                r.validate(data)

    def test_each_causal_stage_needs_explicit_text(self):
        for field in ('scenario', 'failure', 'cause', 'features', 'mechanism', 'effect', 'limits', 'countercheck', 'next_action'):
            data = copy.deepcopy(self.data)
            data['causal_review']['chains'][0].pop(field)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                r.validate(data)

    def test_missing_independent_claim_is_rejected(self):
        self.data['search'].append({**copy.deepcopy(self.data['search'][0]), 'claim': '权 9'})
        with self.assertRaisesRegex(ValueError, '全部独立'):
            r.validate(self.data)

    def test_indexed_independent_cannot_be_omitted_from_causal_review(self):
        self.data['search'] = []
        for type_fields in ({'kind': '独立'}, {'kind': '方法独立项'}, {'kind': 'Independent claim'},
                            {'kind': '系统项，引用装置', 'claim_type': 'independent'}):
            data = copy.deepcopy(self.data)
            data['claim_index'].append({'claim': '权 9', 'path': '9', 'summary': '另一独立项', **type_fields})
            with self.subTest(kind=type_fields), self.assertRaisesRegex(ValueError, '全部独立权利要求：权 9'):
                r.validate(data)

    def test_indexed_independent_can_be_covered_without_search(self):
        self.data['search'] = []
        self.data['claim_index'].append({'claim': 'Claim 9', 'kind': 'System claim', 'claim_type': 'independent',
                                         'path': '9', 'summary': '独立系统项'})
        self.review['targets'].append({'id': 'T9', 'claim': 'Claim 9', 'kind': 'independent', 'path': '9'})
        self.review['chains'].append({**copy.deepcopy(self.chain), 'id': 'C9', 'target_id': 'T9'})
        r.validate(self.data)

    def test_index_cannot_disagree_with_target_or_search_type(self):
        row = self.data['claim_index'][0]
        row.update(kind='独立权利要求', claim_type='dependent')
        with self.assertRaisesRegex(ValueError, '与速览显示类型'):
            r.validate(self.data)
        row.update(kind='从属权利要求', claim_type='dependent')
        for fields in ('search', 'targets'):
            data = copy.deepcopy(self.data)
            if fields == 'targets':
                data['search'] = []
            else:
                data['causal_review']['targets'][0]['kind'] = 'dependent'
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, '权项 权 1.*类型矛盾'):
                r.validate(data)

    def test_ambiguous_legacy_index_needs_a_known_type(self):
        self.data['claim_index'][0].pop('claim_type', None)
        self.data['claim_index'][0]['kind'] = '装置项'
        r.validate(self.data)  # The registered target and search establish the legacy type.
        row = self.data['claim_index'][1]
        row.pop('claim_type', None)
        row['kind'] = '程序项，执行方法'
        with self.assertRaisesRegex(ValueError, '权 2.*请填 claim_type'):
            r.validate(self.data)
        for kind in ('择一从属项，引用独立权利要求1或权3', '从属权利要求2引用独立权利要求1'):
            with self.subTest(kind=kind):
                row['kind'] = kind
                r.validate(self.data)

    def test_missing_problem_and_alternative_path_are_rejected(self):
        for field, row in [('problems', {'id':'P2','statement':'另一个效果主张','location':'背景[0003]'}),
                           ('targets', {'id':'T2','claim':'权 1','kind':'independent','path':'另一备选路径'})]:
            data = copy.deepcopy(self.data)
            data['causal_review'][field].append(row)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, '逐项覆盖'):
                r.validate(data)

    def test_each_link_needs_its_own_evidence(self):
        self.chain['evidence'] = self.chain['evidence'][:2]
        with self.assertRaisesRegex(ValueError, '分别记录'):
            r.validate(self.data)

    def test_assumption_cannot_be_marked_supported(self):
        self.chain.update(status='supported', gaps=[])
        with self.assertRaisesRegex(ValueError, '待验证假设'):
            r.validate(self.data)

    def test_reasoned_inference_does_not_require_experiment(self):
        self.chain.update(status='supported', gaps=[], issues=[], effect='限定工况内增加光源供给。')
        self.chain['evidence'][2].update(kind='inference', location='光源控制原理与已给定开启动作',
                                       quote='低于阈值时开灯。', reason='仅推得发光器通电，不推得量化照度、生长或边界动作。')
        self.assertIn('已逐项记录技术因果依据', self.render())

    def test_supported_chain_cannot_keep_gap(self):
        self.chain['status'] = 'supported'
        with self.assertRaisesRegex(ValueError, '有缺口'):
            r.validate(self.data)

    def test_missing_gap_and_missing_issue_are_rejected(self):
        for field in ('gaps', 'issues'):
            data = copy.deepcopy(self.data)
            data['causal_review']['chains'][0][field] = []
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, '明确具体缺口'):
                r.validate(data)

    def test_critical_gap_cannot_be_low_priority(self):
        self.data['issues'][0]['priority'] = 'low'
        with self.assertRaisesRegex(ValueError, '高优先级'):
            r.validate(self.data)

    def test_independent_gap_cannot_be_downgraded(self):
        self.chain['critical'] = False
        with self.assertRaisesRegex(ValueError, '必须标为关键'):
            r.validate(self.data)

    def test_secondary_dependent_gap_still_has_visible_issue(self):
        self.review['targets'].append({'id':'T2','claim':'权 2','kind':'dependent','path':'1 → 2'})
        extra = copy.deepcopy(self.chain)
        extra.update(id='C2', target_id='T2', critical=False)
        self.review['chains'].append(extra)
        self.assertIn('C2', self.render())

    def test_unresolved_chain_cannot_link_only_resolved_or_rejected(self):
        for state in ('resolved', 'rejected'):
            data = copy.deepcopy(self.data)
            data['actions'] = []
            data['issues'][0]['status'] = state
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, '不能全部标为'):
                r.validate(data)

    def test_broken_or_duplicate_references_are_rejected(self):
        for field, value in [('target_id','missing'), ('problem_id','missing'),
                             ('issues',['missing']), ('issues',['EX-01','EX-01'])]:
            data = copy.deepcopy(self.data)
            data['causal_review']['chains'][0][field] = value
            with self.subTest(field=field,value=value), self.assertRaises(ValueError):
                r.validate(data)

    def test_legacy_reports_have_visible_unreviewed_notice(self):
        legacy = json.loads((ROOT / 'tests/fixtures/legacy-input.json').read_text(encoding='utf8'))
        for version in (2, 3):
            legacy['schema_version'] = version
            self.assertIn('技术因果必查未完成', self.render(legacy))

    def test_not_applicable_needs_reason_and_cannot_hide_claims(self):
        self.review.update(applicability='not_applicable', targets=[], problems=[], chains=[])
        with self.assertRaisesRegex(ValueError, '已有权项'):
            r.validate(self.data)
        self.data.update(search=[], claim_index=[], evidence=[])
        self.review['scope'] = '仅审查外观图样，不主张功能性结构或技术效果。'
        self.assertIn('因果必查适用范围', self.render())

    def test_claim_evidence_alone_blocks_not_applicable(self):
        self.data.pop('claim_index', None)
        self.data['search'] = []
        self.review.update(applicability='not_applicable', targets=[], problems=[], chains=[])
        with self.assertRaisesRegex(ValueError, '已有权项记录.*权项对照'):
            r.validate(self.data)

    def test_amendment_alone_blocks_not_applicable(self):
        data = json.loads((ROOT / 'examples/amendment-input.json').read_text(encoding='utf8'))
        data.update(schema_version=4, claim_index=[], search=[], evidence=[])
        data['causal_review'] = {'applicability': 'not_applicable', 'scope': '仅审查外观图样。',
                                 'targets': [], 'problems': [], 'chains': []}
        with self.assertRaisesRegex(ValueError, '已有权项记录.*权项修改候选'):
            r.validate(data)

    def test_declared_gaps_across_domains_stay_explicit(self):
        cases = [('机械', '外壳散热不证明轴承润滑改善'), ('软件', '平均误差降低不证明漏报率下降'),
                 ('材料', '拉伸强度提高不证明连接处疲劳寿命增加')]
        for domain, gap in cases:
            self.chain.update(gaps=[gap], cause=gap, countercheck=gap)
            output = self.render()
            self.assertGreaterEqual(output.count(gap), 2, domain)

    def test_sources_and_gap_text_are_escaped_and_links_resolve(self):
        text = '<script>bad()</script> & "quote"'
        self.chain['evidence'][0]['quote'] = text
        self.chain['gaps'] = [text]
        output = self.render()
        self.assertNotIn('<script>bad()', output)
        self.assertIn('&lt;script&gt;', output)
        doc = Document(output)
        self.assertEqual(len(doc.ids), len(set(doc.ids)))
        self.assertFalse(set(doc.links) - set(doc.ids))

    def test_amendment_workflow_remains_available_under_schema4(self):
        candidate = json.loads((ROOT / 'examples/amendment-input.json').read_text(encoding='utf8'))
        candidate['schema_version'] = 4
        # Verify integration using its own independent-claim name and issue ID.
        candidate['causal_review'] = copy.deepcopy(self.review)
        candidate['causal_review']['targets'][0]['claim'] = candidate['search'][0]['claim']
        candidate['causal_review']['chains'][0]['issues'] = [candidate['issues'][0]['id']]
        candidate['issues'][0].update(priority='high', status='pending')
        self.assertIn('id="amendments"', self.render(candidate))


if __name__ == '__main__':
    unittest.main()
