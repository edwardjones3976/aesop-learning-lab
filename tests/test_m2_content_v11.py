"""V11 replaces only the day-seven recursion item; historical v10 is frozen."""
import json
from pathlib import Path
import unittest

from aesop_lab.content import load_pack
from aesop_lab.experiment.descriptive_v8 import DESCRIPTIVE_V8

ROOT = Path(__file__).resolve().parents[1] / 'content/packs/python-functions-recursion'
NEW_ID = 'recursion-week-01-v11'
OLD_ID = 'recursion-week-01-v9'
FAMILY = 'recursion-converge-week-v8'


def without_versions(value):
    if isinstance(value, dict):
        return {k: without_versions(v) for k, v in value.items()
                if k not in ('content_version', 'pack_version')}
    if isinstance(value, list):
        return [without_versions(v) for v in value]
    return value


class M2ContentV11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = json.loads((ROOT / 'pack-m2-draft.10.json').read_text(encoding='utf-8'))
        cls.raw = json.loads((ROOT / 'pack-m2-draft.11.json').read_text(encoding='utf-8'))
        cls.pack = load_pack(ROOT / 'pack-m2-draft.11.json')
        cls.new = next(i for i in cls.raw['items'] if i['id'] == NEW_ID)

    def test_identity_and_only_one_replacement(self):
        self.assertEqual(self.pack.pack_version, 'm2-draft.11')
        self.assertEqual(self.pack.status, 'draft')
        for section in ('concepts', 'lessons', 'items'):
            self.assertEqual({i['content_version'] for i in self.raw[section]}, {'v11'})
        self.assertNotIn(OLD_ID, {i['id'] for i in self.raw['items']})
        old = without_versions(self.old)
        new = without_versions(self.raw)
        old['items'] = [i for i in old['items'] if i['id'] != OLD_ID]
        new['items'] = [i for i in new['items'] if i['id'] != NEW_ID]
        # The review note is the one pack-level field that must describe the v11 change;
        # every other review field (such as receipts) must still match v10.
        note = new['review'].pop('note')
        old['review'].pop('note')
        self.assertIn(OLD_ID, note)
        self.assertIn(NEW_ID, note)
        self.assertNotIn('unchanged from v9', note)
        self.assertEqual(new, old)
        # Also compare exact serialized item bytes after the sole version replacement.
        old_text = (ROOT / 'pack-m2-draft.10.json').read_text(encoding='utf-8')
        new_text = (ROOT / 'pack-m2-draft.11.json').read_text(encoding='utf-8')
        for item in old['items']:
            marker = '    {\n      "id": "' + item['id'] + '"'
            a, b = old_text.index(marker), new_text.index(marker)
            self.assertEqual(old_text[a:old_text.index('\n    }', a)].replace('"v10"', '"v11"'),
                             new_text[b:new_text.index('\n    }', b)])
        self.assertEqual(sum(i['held_out'] for i in new['items']), 9)

    def test_new_key_executes_to_six(self):
        namespace = {}
        exec(self.new['body'], namespace)
        self.assertEqual(namespace['result'], 6)
        # Each common mistake must lead to a different answer than the key.
        def misread(low, high, step_high, answer_high, stop_early):
            while not (low >= high or (stop_early and low + 2 >= high - step_high)):
                low, high = low + 2, high - step_high
            return high if answer_high else low
        mistakes = {'returns high': misread(0, 8, 1, True, False),
                    'one call early': misread(0, 8, 1, False, True),
                    'moves only low': misread(0, 8, 0, False, False)}
        self.assertEqual(mistakes, {'returns high': 5, 'one call early': 4, 'moves only low': 8})
        self.assertEqual(self.new['answer_key'], {'status': 'candidate', 'accepted': [str(namespace['result'])]})
        self.assertEqual(self.new['check_expression'], 'result')
        self.assertEqual([h['level'] for h in self.new['hints']], ['nudge', 'targeted', 'worked_solution'])
        old = next(i for i in self.old['items'] if i['id'] == OLD_ID)
        for key in ('evidence_kind', 'difficulty', 'learning_objective', 'source_ids'):
            self.assertEqual(self.new[key], old[key])
        self.assertEqual((self.new['held_out'], self.new['check_delay_days']), (True, 7))

    def test_primary_family_is_unencountered_before_check(self):
        self.assertEqual(self.new['family_id'], FAMILY)
        self.assertEqual(dict(DESCRIPTIVE_V8.primary_family_by_concept)['recursion-as-self-call'], FAMILY)
        for lesson in self.raw['lessons']:
            self.assertNotIn(FAMILY, lesson['encountered_family_ids'])
            self.assertNotIn('def meet(', lesson['body'])
        for item in self.raw['items']:
            if item['id'] != NEW_ID:
                self.assertNotEqual(item['family_id'], FAMILY)
                self.assertNotIn('def meet(', json.dumps(item))


if __name__ == '__main__':
    unittest.main()
