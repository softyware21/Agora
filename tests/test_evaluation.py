import copy
import json
import unittest

import evaluation


def answer(values):
    return '```agora-evaluation\n' + json.dumps(values) + '\n```'


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.case = evaluation.load_cases()[0]

    def test_exact_numbers_and_wrong_conclusions(self):
        self.assertEqual(evaluation.grade(answer({'final_price': '192/2', 'unchanged': 'no'}), self.case)['status'], 'pass')
        self.assertEqual(evaluation.grade(answer({'final_price': '96', 'unchanged': 'yes'}), self.case)['status'], 'fail')
        self.assertEqual(evaluation.grade(answer({'final_price': '96.00001', 'unchanged': 'no'}), self.case)['status'], 'fail')

    def test_missing_duplicate_extra_and_invalid_fields_are_not_passes(self):
        valid = answer(self.case['expected'])
        invalid = ['The answer is 96.', valid + '\n' + valid, answer({'final_price': 96, 'unchanged': 'no'}),
                   answer({'final_price': '1/0', 'unchanged': 'no'}), answer({'unchanged': 'no'}),
                   answer(dict(self.case['expected'], extra='no')),
                   '```agora-evaluation\n{"final_price":"96","final_price":"100","unchanged":"no"}\n```']
        for text in invalid:
            with self.subTest(text=text):
                self.assertEqual(evaluation.grade(text, self.case)['status'], 'format_error')
        self.assertEqual(evaluation.grade(None, self.case)['status'], 'pending')

    def test_abstention_requires_the_right_case(self):
        case = evaluation.load_cases()[3]
        self.assertEqual(evaluation.grade(answer(case['expected']), case)['status'], 'pass')
        self.assertEqual(evaluation.grade(answer({'answerability': 'determined', 'percent': '12'}), case)['status'], 'fail')
        self.assertEqual(evaluation.grade(answer({'final_price': 'unknown', 'unchanged': 'no'}), self.case)['status'], 'format_error')

    def test_answer_key_and_rationale_never_enter_rules(self):
        changed = copy.deepcopy(self.case)
        changed['expected']['final_price'] = '987654321'
        changed['rationale'] = 'PRIVATE_KEY_MARKER'
        self.assertEqual(evaluation.rules(changed), evaluation.rules(self.case))
        self.assertNotIn('PRIVATE_KEY_MARKER', evaluation.rules(changed))

    def test_unsafe_ids_and_bad_keys_are_rejected(self):
        for edit in (lambda c: c.update(id='../escape'), lambda c: c.update(expected={}),
                     lambda c: c.update(fields={'value': 'unsupported'})):
            case = copy.deepcopy(self.case)
            edit(case)
            with self.assertRaises(ValueError):
                evaluation.validate_cases([case])
        with self.assertRaises(ValueError):
            evaluation.validate_cases([self.case, self.case])

    def test_comparison_can_show_regressions_not_only_improvements(self):
        good = answer(self.case['expected'])
        bad = answer({'final_price': '100', 'unchanged': 'yes'})
        record = {'turns': [{'provider': 'codex', 'phase': 'initial', 'text': good},
                            {'provider': 'claude', 'phase': 'initial', 'text': bad},
                            {'provider': 'codex', 'phase': 'summary', 'text': bad}]}
        scores = evaluation.compare(record, self.case)
        self.assertEqual([scores[n]['status'] for n in ('codex', 'claude', 'debate')], ['pass', 'fail', 'fail'])
        record['turns'][-1]['text'] = good
        self.assertEqual(evaluation.compare(record, self.case)['debate']['status'], 'pass')
