import json
import unittest

import evidence


def answer(claims):
    return 'Analysis.\n```agora-calculations\n' + json.dumps(claims) + '\n```'


def claim(expression='1000 * 10 * 30 * 0.01', expected='3000'):
    return {'claim': 'Monthly call cost', 'expression': expression, 'expected': expected, 'unit': 'USD'}


class EvidenceTests(unittest.TestCase):
    def test_arithmetic_match_does_not_verify_claim(self):
        result = evidence.check_answer(answer([claim()]), 2)
        check = result['checks'][0]
        self.assertEqual(check['id'], 'T002-C01')
        self.assertEqual(check['status'], 'arithmetic_match')
        self.assertEqual(check['scope'], 'arithmetic_only')
        self.assertIn('not been verified', check['reason'])

    def test_false_and_rounded_results_are_flagged(self):
        for item in [claim(expected='500'), claim('500 / 3000 * 100', '16.7')]:
            with self.subTest(item=item):
                check = evidence.check_answer(answer([item]), 1)['checks'][0]
                self.assertEqual(check['status'], 'arithmetic_mismatch')
        check = evidence.check_answer(answer([claim('500 / 3000 * 100', '50/3')]), 1)['checks'][0]
        self.assertEqual(check['status'], 'arithmetic_match')

    def test_no_declaration_does_not_imply_verification(self):
        result = evidence.check_answer('Both models agree that 2 + 2 = 5.', 1)
        self.assertEqual(result['status'], 'not_declared')
        self.assertEqual(result['checks'], [])

    def test_bad_blocks_stay_unverified(self):
        for text in ['```agora-calculations\n[]', '```agora-calculations\nnot json\n```',
                     answer({}), answer([claim()] * 11), answer([]) + '\n' + answer([])]:
            with self.subTest(text=text):
                result = evidence.check_answer(text, 1)
                self.assertEqual(result['status'], 'invalid')
                self.assertFalse(result['checks'])

    def test_bad_entry_does_not_drop_other_checks(self):
        result = evidence.check_answer(answer([claim(), None, claim('1/0', '0')]), 1)
        self.assertEqual([c['status'] for c in result['checks']],
                         ['arithmetic_match', 'unverified', 'unverified'])

    def test_rejects_code_and_numeric_json_values(self):
        for item in [claim('__import__("os").getcwd()', '0'), claim(expected=3000),
                     claim(expected='1000*3'), claim(expected='NaN')]:
            with self.subTest(item=item):
                check = evidence.check_answer(answer([item]), 1)['checks'][0]
                self.assertEqual(check['status'], 'unverified')

    def test_ledger_keeps_each_turn_separate(self):
        turns = [{'text': answer([claim()]), 'provider': name, 'phase': 'initial', 'round': 0}
                 for name in ['codex', 'claude']]
        checks = evidence.ledger(turns)
        self.assertEqual(checks[0]['checks'][0]['id'], 'T001-C01')
        self.assertEqual(checks[1]['checks'][0]['id'], 'T002-C01')
