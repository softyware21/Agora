import json
import unittest

from evals.summary_fidelity import cases, grade, prompt


class SummaryFidelityTests(unittest.TestCase):
    def setUp(self):
        self.items = cases()
        self.rows = [{'id': c['id'], 'verdict': c['expected'], 'reason': 'Comparison explanation.'}
                     for c in self.items]

    def test_prompt_excludes_keys(self):
        items = [dict(c, expected='SECRET_KEY', rationale='SECRET_REASON') for c in self.items]
        self.assertNotIn('SECRET', prompt(items))

    def test_grades_false_alarms_misses_and_abstentions(self):
        self.assertEqual(grade(json.dumps(self.rows), self.items)['correct'], 8)
        self.rows[0]['verdict'] = 'faithful'
        self.rows[1]['verdict'] = 'distorted'
        self.rows[2]['verdict'] = 'uncertain'
        result = grade(json.dumps(self.rows), self.items)
        self.assertEqual((result['correct'], result['misses'], result['false_alarms'], result['uncertain']), (5, 1, 1, 1))

    def test_invalid_and_missing_responses_do_not_pass(self):
        duplicate = self.rows[:-1] + [self.rows[0]]
        for value in (self.rows[:-1], duplicate, {}, [None] * 8):
            self.assertFalse(grade(json.dumps(value), self.items)['valid'])
        self.assertFalse(grade('[{"id":"C1","id":"C2"}]', self.items)['valid'])
        self.assertFalse(grade('No result', self.items)['valid'])

    def test_accepts_only_one_complete_json_fence(self):
        fenced = '```json\n' + json.dumps(self.rows) + '\n```'
        self.assertEqual(grade(fenced, self.items)['correct'], 8)
        for text in (fenced + '\n' + fenced, 'Explanation\n' + fenced, fenced + '\nTrailing text'):
            self.assertFalse(grade(text, self.items)['valid'])

    def test_korean_cases_cover_abstention_without_exposing_keys(self):
        items = cases('korean')
        self.assertEqual(len({item['id'] for item in items}), 6)
        self.assertEqual({item['expected'] for item in items}, {'faithful', 'distorted', 'uncertain'})
        for item in items:
            visible = prompt([item])
            self.assertNotIn(item['rationale'], visible)
            self.assertNotIn('"expected"', visible)
            rows = [{'id': item['id'], 'verdict': item['expected'], 'reason': 'Comparison.'}]
            self.assertEqual(grade(json.dumps(rows), [item])['correct'], 1)
