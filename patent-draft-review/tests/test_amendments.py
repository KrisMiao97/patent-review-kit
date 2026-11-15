"""Regressions for evidence-backed amendment options and older inputs."""
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


class AmendmentTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'examples/amendment-input.json').read_text(encoding='utf-8'))
        self.item = self.data['amendment_options'][0]

    def test_complete_candidate_links_and_evidence_are_rendered(self):
        with tempfile.TemporaryDirectory() as folder:
            output = r.render(r.validate(self.data), Path(folder))
        document = Document(output)
        self.assertFalse(set(document.links) - set(document.ids))
        self.assertEqual(len(document.ids), len(set(document.ids)))
        self.assertIn('实施例组合依据', output)
        self.assertIn(self.item['text'], output)
        self.assertIn('省略特征及理由', output)

    def test_no_options_remains_compatible(self):
        self.data.pop('amendment_options')
        with tempfile.TemporaryDirectory() as folder:
            output = r.render(r.validate(self.data), Path(folder))
        self.assertNotIn('id="amendments"', output)

    def test_empty_options_remains_compatible(self):
        self.data['amendment_options'] = []
        with tempfile.TemporaryDirectory() as folder:
            output = r.render(r.validate(self.data), Path(folder))
        self.assertNotIn('id="amendments"', output)

    def test_missing_combination_and_unknown_source_are_rejected(self):
        for change in ('combination', 'source'):
            data = copy.deepcopy(self.data)
            item = data['amendment_options'][0]
            if change == 'combination':
                item.pop('combination')
            else:
                item['features'][0]['source_ids'] = ['missing']
            with self.subTest(change=change), self.assertRaises(ValueError):
                r.validate(data)

    def test_supported_combination_cannot_hide_partial_features(self):
        self.item['features'][0]['status'] = 'partial'
        with self.assertRaisesRegex(ValueError, '逐特征依据'):
            r.validate(self.data)
        self.item['combination']['status'] = 'partial'
        r.validate(self.data)

    def test_combination_must_cover_each_feature(self):
        self.item['combination']['source_ids'] = ['S1']
        with self.assertRaisesRegex(ValueError, '覆盖'):
            r.validate(self.data)

    def test_claim_dependency_alone_cannot_prove_combination(self):
        for source in self.item['sources']:
            source['kind'] = 'claim'
        with self.assertRaisesRegex(ValueError, '来源类型'):
            r.validate(self.data)

    def test_unknown_phase_cannot_offer_current_draft(self):
        self.data['phase'] = 'unknown'
        for issue in self.data['issues']:
            for edit in issue['edits']:
                edit['applicability']['kind'] = 'review'
        with self.assertRaisesRegex(ValueError, '程序阶段'):
            r.validate(self.data)

    def test_duplicate_options_and_sources_are_rejected(self):
        for field in ('options', 'sources'):
            data = copy.deepcopy(self.data)
            if field == 'options':
                data['amendment_options'].append(copy.deepcopy(self.item))
            else:
                data['amendment_options'][0]['sources'].append(copy.deepcopy(self.item['sources'][0]))
            with self.subTest(field=field), self.assertRaises(ValueError):
                r.validate(data)

    def test_missing_evidence_remains_visible(self):
        self.item['sources'] = []
        for feature in self.item['features']:
            feature.update(status='unverified', source_ids=[])
        self.item['combination'].update(status='unverified', source_ids=[])
        with tempfile.TemporaryDirectory() as folder:
            output = r.render(r.validate(self.data), Path(folder))
        self.assertIn('未列来源', output)
        self.assertIn('待核验', output)

    def test_candidate_and_quotes_are_escaped(self):
        self.item['text'] = '<script>alert(1)</script>'
        self.item['sources'][0]['quote'] = '<img onerror="x">'
        with tempfile.TemporaryDirectory() as folder:
            output = r.render(r.validate(self.data), Path(folder))
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', output)
        self.assertNotIn('<img onerror=', output)

    def add_claim_source(self):
        source = copy.deepcopy(self.item['sources'][0])
        source.update(id='C1', kind='claim', embodiment_ids=[])
        self.item['sources'].append(source)
        return source

    def cross_embodiment(self):
        self.item['embodiments'].append({'id': 'E2', 'label': '虚构实施例二'})
        self.item['sources'][1]['embodiment_ids'] = ['E2']
        guide = copy.deepcopy(self.item['sources'][0])
        guide.update(id='G', quote='实施例一的灯可与实施例二的传感器按所述控制关系组合。', embodiment_ids=['E1', 'E2'],
                     combination_guidance={'embodiment_ids':['E1','E2'], 'relation':'将实施例一的灯与实施例二的传感器用于同一控制关系。'})
        self.item['sources'].append(guide)
        self.item['combination'].update(mode='explicit_combination', embodiment_ids=['E1', 'E2'],
                                        source_ids=['S1', 'S2', 'G'], guidance_source_ids=['G'])

    def test_claims_plus_unrelated_description_cannot_support_features(self):
        self.add_claim_source()
        for feature in self.item['features']:
            feature.update(source_ids=[], claim_source_ids=['C1'])
        # Description sources remain at combination level: they cannot fill feature gaps.
        with self.assertRaisesRegex(ValueError, '对应说明书或附图'):
            r.validate(self.data)

    def test_claim_path_can_coexist_with_real_feature_evidence(self):
        self.add_claim_source()
        self.item['features'][0]['claim_source_ids'] = ['C1']
        r.validate(self.data)
        with tempfile.TemporaryDirectory() as folder:
            output = r.render(self.data, Path(folder))
        self.assertIn('权项路径', output)
        self.assertIn(r.amendment_anchor('D-01', 'C1'), output)

    def test_sources_cannot_be_relabelled_as_claim_path_or_guidance(self):
        for field in ('claim_source_ids', 'guidance_source_ids'):
            self.setUp()
            self.add_claim_source()
            if field == 'claim_source_ids':
                self.item['features'][0][field] = ['S1']
            else:
                self.item['combination'][field] = ['C1']
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, '来源类型'):
                r.validate(self.data)

    def test_different_labels_can_refer_to_same_embodiment(self):
        self.item['sources'][0]['embodiment'] = '第一种写法'
        self.item['combination']['embodiment'] = '同一对象的另一种写法'
        r.validate(self.data)

    def test_shared_disclosure_remains_valid_for_one_selected_embodiment(self):
        self.item['embodiments'].append({'id':'E2','label':'第二实施例'})
        source = self.item['sources'][0]
        source.update(embodiment_ids=['E1','E2'], quote='实施例一和二均使用相同的箱体和托盘。')
        with tempfile.TemporaryDirectory() as folder:
            html = r.render(r.validate(self.data), Path(folder))
        self.assertIn('同一实施例 · E1', html)
        self.assertIn('E1, E2', html)
        self.assertNotIn('跨实施例指引', html)

    def test_source_from_another_embodiment_is_rejected(self):
        self.item['embodiments'].append({'id': 'E2', 'label': '第二实施例'})
        self.item['sources'][1]['embodiment_ids'] = ['E2']
        with self.assertRaisesRegex(ValueError, '未归属于所选实施例'):
            r.validate(self.data)

    def test_supported_evidence_needs_known_embodiment_membership(self):
        for ids in ([], ['missing'], ['E1', 'E1']):
            self.setUp()
            self.item['sources'][0]['embodiment_ids'] = ids
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                r.validate(self.data)

    def test_explicit_cross_embodiment_guidance_is_allowed(self):
        self.cross_embodiment()
        with tempfile.TemporaryDirectory() as folder:
            html = r.render(r.validate(self.data), Path(folder))
        self.assertIn('E1、E2 · 将实施例一的灯与实施例二的传感器', html)
        self.assertFalse(set(Document(html).links) - set(Document(html).ids))

    def test_membership_coverage_alone_does_not_show_combination(self):
        for guidance in (['S1','S2'], ['G']):
            self.setUp()
            self.cross_embodiment()
            self.item['sources'][2].pop('combination_guidance')
            self.item['sources'][2]['quote'] = '实施例一和二分别使用相同的箱体。'
            self.item['combination']['guidance_source_ids'] = guidance
            with self.subTest(guidance=guidance), self.assertRaisesRegex(ValueError, '缺少明确连接'):
                r.validate(self.data)
            self.item['combination']['status'] = 'partial'
            r.validate(self.data)

    def test_guidance_must_link_multiple_embodiments_supported_by_its_source(self):
        for ids in (['E1'], ['E1','E3'], ['E1','E1']):
            self.setUp()
            self.cross_embodiment()
            self.item['embodiments'].append({'id':'E3','label':'第三实施例'})
            self.item['sources'][2]['combination_guidance']['embodiment_ids'] = ids
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                r.validate(self.data)

    def test_multiple_guidance_sources_must_connect_all_selected_embodiments(self):
        self.cross_embodiment()
        for id in ('E3', 'E4'):
            self.item['embodiments'].append({'id':id,'label':id})
        self.item['combination']['embodiment_ids'].extend(['E3','E4'])
        first_guide = self.item['sources'][2]
        for id, connected in [('G34',['E3','E4']), ('G23',['E2','E3'])]:
            guide = dict(first_guide, id=id, embodiment_ids=connected, quote=f'原文明确可组合 {"、".join(connected)}。',
                         combination_guidance={'embodiment_ids':connected,'relation':f'明确连接 {"、".join(connected)} 的对应特征。'})
            self.item['sources'].append(guide)
        combo = self.item['combination']
        combo['source_ids'].extend(['G34','G23'])
        combo['guidance_source_ids'].append('G34')
        with self.assertRaisesRegex(ValueError, '未连接全部'):
            r.validate(self.data)
        combo['guidance_source_ids'].append('G23')
        r.validate(self.data)

    def test_guidance_cannot_rely_on_an_unselected_embodiment(self):
        self.cross_embodiment()
        self.item['embodiments'].append({'id':'E3','label':'第三实施例'})
        source = self.item['sources'][2]
        source['embodiment_ids'].append('E3')
        source['combination_guidance']['embodiment_ids'].append('E3')
        with self.assertRaisesRegex(ValueError, '涉及未选实施例'):
            r.validate(self.data)

    def test_cross_embodiment_without_complete_guidance_is_rejected(self):
        for field, value in (('guidance_source_ids', []), ('guidance_source_ids', ['S1']),
                             ('source_ids', ['S1', 'S2']), ('mode', 'same_embodiment'), ('mode', 'unresolved')):
            self.setUp()
            self.cross_embodiment()
            self.item['combination'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                r.validate(self.data)

    def test_mutually_exclusive_embodiments_reject_supported_but_keep_gap(self):
        self.cross_embodiment()
        self.item['embodiment_conflicts'] = [{'left': 'E1', 'right': 'E2', 'reason': '安装位置互斥，尚无解决条件。'}]
        with self.assertRaisesRegex(ValueError, '已记录互斥'):
            r.validate(self.data)
        self.item['combination']['status'] = 'gap'
        r.validate(self.data)
        with tempfile.TemporaryDirectory() as folder:
            output = r.render(self.data, Path(folder))
        self.assertIn('安装位置互斥，尚无解决条件。', output)
        self.assertIn('依据有缺口', output)

    def test_conflict_references_and_duplicate_pairs_are_checked(self):
        self.cross_embodiment()
        for entries in ([{'left':'E1','right':'missing','reason':'待核'}],
                        [{'left':'E1','right':'E1','reason':'待核'}],
                        [{'left':'E1','right':'E2','reason':'待核'}, {'left':'E2','right':'E1','reason':'待核'}]):
            self.item['embodiment_conflicts'] = entries
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                r.validate(self.data)

    def test_placeholder_and_incomplete_fallback_are_rejected(self):
        for field, value in (('text','略'), ('text','（略）'), ('text','略。'), ('text','【ＴＢＤ】'), ('text','（…）'),
                             ('status','pending'), ('kind','wording')):
            self.setUp()
            if field == 'text': self.item[field] = value
            else: self.item['candidate_check'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                r.validate(self.data)

    def test_complete_independent_and_non_chinese_claim_are_allowed(self):
        self.item['candidate_check']['kind'] = 'independent_claim'
        self.item['text'] = 'An apparatus comprising a container, a lamp slightly above a tray, and a sensor controlling the lamp (optionally).'
        r.validate(self.data)

    def test_confirmed_scope_change_cannot_be_labelled_clarification(self):
        self.item['tier'] = 'clarify'
        for effect in ('narrowed', 'broadened'):
            self.item['scope_check']['effect'] = effect
            with self.subTest(effect=effect), self.assertRaisesRegex(ValueError, '不能标为保守澄清'):
                r.validate(self.data)
        for effect in ('unchanged', 'uncertain'):
            self.item['scope_check']['effect'] = effect
            r.validate(self.data)

    def test_decision_records_are_required_and_unique(self):
        for field in ('candidate_check', 'scope_check', 'claim_actions', 'embodiments', 'embodiment_conflicts'):
            data = copy.deepcopy(self.data)
            data['amendment_options'][0].pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                r.validate(data)
        self.item['claim_actions'].append(copy.deepcopy(self.item['claim_actions'][0]))
        with self.assertRaisesRegex(ValueError, '不得重复'):
            r.validate(self.data)

    def test_invalid_tier_duplicate_features_and_dangling_combo_are_rejected(self):
        for field in ('tier', 'features', 'combination'):
            self.setUp()
            if field == 'tier': self.item[field] = 'invalid'
            elif field == 'features': self.item[field][1]['id'] = self.item[field][0]['id']
            else: self.item[field]['source_ids'].append('missing')
            with self.subTest(field=field), self.assertRaises(ValueError):
                r.validate(self.data)

    def test_old_schemas_cannot_carry_new_amendments(self):
        for version in (1, 2):
            self.data['schema_version'] = version
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'schema_version 3'):
                r.validate_amendments(self.data, {'EX-01'})

    def test_old_candidate_records_need_explicit_migration(self):
        self.item['features'][0].pop('claim_source_ids')
        with self.assertRaisesRegex(ValueError, 'claim_source_ids'):
            r.validate(self.data)

    def test_adversarial_ids_cannot_collide_with_sources(self):
        second = copy.deepcopy(self.item)
        second['id'] = 'D-01-source-S1'
        self.data['amendment_options'].append(second)
        with tempfile.TemporaryDirectory() as folder:
            output = r.render(r.validate(self.data), Path(folder))
        document = Document(output)
        self.assertEqual(len(document.ids), len(set(document.ids)))
        self.assertFalse(set(document.links) - set(document.ids))
        self.assertNotEqual(r.amendment_anchor('A-B', 'C'), r.amendment_anchor('A', 'B-C'))
        self.assertNotEqual(r.amendment_anchor('D-01', 'S1'), r.amendment_anchor('D-01-source-S1'))

    def test_new_decision_and_embodiment_fields_are_escaped(self):
        payload = '<img src=x onerror=alert(1)>'
        self.item['scope_check']['reason'] = payload
        self.item['claim_actions'][0]['reason'] = payload
        self.item['embodiments'][0]['label'] = payload
        with tempfile.TemporaryDirectory() as folder:
            output = r.render(r.validate(self.data), Path(folder))
        self.assertNotIn(payload, output)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', output)


if __name__ == '__main__':
    unittest.main()
