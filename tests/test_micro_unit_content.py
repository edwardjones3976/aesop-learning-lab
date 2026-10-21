"""Each broken fixture asserts the specific issue path and code for its rule."""
import json
from pathlib import Path
import unittest
from aesop_lab.content import ContentValidationError
from aesop_lab.content.micro_unit import load_micro_unit_pack, parse_micro_unit_pack, validate_micro_unit_pack

FIXTURE = Path(__file__).parent / 'fixtures' / 'micro-unit-sample.json'

class MicroUnitPackTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.unit = self.raw['units'][0]
        self.check = self.unit['check']

    def rejects(self, path, code):
        self.assertIn((path, code), {(i.path, i.code) for i in validate_micro_unit_pack(self.raw)})
        with self.assertRaises(ContentValidationError):
            parse_micro_unit_pack(self.raw)

    def test_fixture_and_teaching_reveal(self):
        self.assertEqual(validate_micro_unit_pack(self.raw), ())
        pack = load_micro_unit_pack(FIXTURE)
        self.assertEqual((len(pack.methods), len(pack.units)), (3, 4))
        self.assertEqual(sum(len(u.practice) for u in pack.units), 1)
        self.assertTrue(all(u.check.answer_key.status == 'candidate' for u in pack.units))
        with self.assertRaises(TypeError):
            pack.units[0].variants['extra'] = 'bad'

    def test_missing_variant(self):
        del self.unit['variants']['cued_retrieval']
        self.rejects('units[0].variants.cued_retrieval', 'missing_variant')

    def test_unknown_variant(self):
        self.unit['variants']['unknown'] = 'Lesson'
        self.rejects('units[0].variants.unknown', 'unknown_method')

    def test_duplicate_unit(self):
        self.raw['units'][1]['id'] = self.unit['id']
        self.rejects('units[1].id', 'duplicate_id')

    def test_duplicate_family(self):
        self.raw['units'][1]['check']['family_id'] = self.check['family_id']
        self.rejects('units[1].check.family_id', 'duplicate_id')

    def test_duplicate_check(self):
        self.raw['units'][1]['check']['id'] = self.check['id']
        self.rejects('units[1].check.id', 'duplicate_id')

    def test_missing_candidate_key(self):
        del self.check['answer_key']
        self.rejects('units[0].check.answer_key', 'missing_field')

    def test_non_candidate_key(self):
        self.check['answer_key']['status'] = 'reviewed'
        self.rejects('units[0].check.answer_key.status', 'candidate_key_required')

    def test_delay(self):
        for delay in (1, 7.0, True, '7', None):
            with self.subTest(delay=delay):
                self.check['check_delay_days'] = delay
                self.rejects('units[0].check.check_delay_days', 'invalid_delay')

    def test_held_out(self):
        self.check['held_out'] = False
        self.rejects('units[0].check.held_out', 'held_out_required')

    def test_prompt_leak(self):
        self.check['prompt'] += ' river'
        self.rejects('units[0].check.prompt', 'answer_leak')

    def test_variant_leak_outside_target(self):
        self.check['answer_key']['accepted'].append('hidden phrase')
        self.unit['variants']['cued_retrieval'] += ' hidden phrase'
        self.rejects('units[0].variants.cued_retrieval', 'answer_leak')

    def test_schema_and_kind(self):
        for field in ('schema_version', 'kind'):
            original = self.raw[field]
            self.raw[field] = 'unknown'
            self.rejects(field, 'unknown_value')
            self.raw[field] = original

    def test_duplicate_method(self):
        self.raw['methods'].append(self.raw['methods'][0].copy())
        self.rejects('methods[3].id', 'duplicate_id')

    def test_empty_answers(self):
        self.check['answer_key']['accepted'] = []
        self.rejects('units[0].check.answer_key.accepted', 'empty_list')

    def test_duplicate_answer(self):
        self.check['answer_key']['accepted'] *= 2
        self.rejects('units[0].check.answer_key.accepted', 'duplicate_answer')

    def test_practice_does_not_allow_check_fields(self):
        self.unit['practice'][0]['held_out'] = True
        self.rejects('units[0].practice[0].held_out', 'unknown_field')

    def test_practice_cannot_share_check_id(self):
        self.unit['practice'][0]['id'] = self.check['id']
        self.rejects('units[0].practice[0].id', 'duplicate_id')

    def test_exactly_one_check_object(self):
        self.unit['check'] = [self.check, self.check]
        self.rejects('units[0].check', 'wrong_type')

    def test_malformed_containers_do_not_crash(self):
        for raw in (None, [], {'methods': None, 'units': [None]}):
            self.assertTrue(validate_micro_unit_pack(raw))

    def test_nonempty_collections(self):
        for field in ('methods', 'units'):
            saved = self.raw[field]
            self.raw[field] = []
            self.rejects(field, 'empty_list')
            self.raw[field] = saved

    def test_required_text_types(self):
        cases = [(self.raw, 'pack_id', 'pack_id'),
                 (self.raw['methods'][0], 'name', 'methods[0].name'),
                 (self.raw['methods'][0], 'description', 'methods[0].description'),
                 (self.unit['target'], 'word', 'units[0].target.word'),
                 (self.unit['target'], 'gloss', 'units[0].target.gloss'),
                 (self.unit['variants'], 'cued_retrieval', 'units[0].variants.cued_retrieval'),
                 (self.check, 'prompt', 'units[0].check.prompt')]
        for container, field, path in cases:
            saved = container[field]
            for invalid in ('', '   ', None, [], 7):
                with self.subTest(path=path, value=invalid):
                    container[field] = invalid
                    self.rejects(path, 'wrong_type')
            container[field] = saved

    def test_all_issues_collected(self):
        self.check['held_out'] = False
        self.check['check_delay_days'] = 1
        self.assertEqual({i.code for i in validate_micro_unit_pack(self.raw)}, {'held_out_required', 'invalid_delay'})

if __name__ == '__main__':
    unittest.main()
