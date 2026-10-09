import json
import unittest

import attribution


def summary(entries):
    return '```agora-attributions\n' + json.dumps(entries) + '\n```'


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.turns = [dict(provider=n, phase=p, round=r, text=text)
                      for n, p, r, text in [('codex', 'initial', 0, 'Initial answer A.'),
                                            ('claude', 'initial', 0, 'Initial answer B.'),
                                            ('codex', 'review', 1, 'I agree with the initial conclusion.'),
                                            ('claude', 'review', 1, 'A new qualification appears here.')]]

    def declaration(self, **changes):
        entry = dict(claim='A accepted a point.', turn_id='T003',
                     quote='I agree with the initial conclusion.', responds_to='T002')
        return dict(entry, **changes)

    def test_same_round_later_claim_cannot_be_treated_as_seen(self):
        result = attribution.check(summary([self.declaration(responds_to='T004')]), self.turns)
        self.assertEqual(result['checks'][0]['status'], 'context_not_available')
        reverse = self.declaration(turn_id='T004', quote=self.turns[3]['text'], responds_to='T003')
        self.assertEqual(attribution.check(summary([reverse]), self.turns)['checks'][0]['status'], 'context_not_available')

    def test_matching_quote_is_not_semantic_verification(self):
        result = attribution.check(summary([self.declaration(claim='A accepted every possible point.')]), self.turns)
        self.assertEqual(result['checks'][0]['status'], 'quote_and_context_match')
        self.assertIn('unverified', result['checks'][0]['reason'])

    def test_fabricated_quote_wrong_speaker_and_unknown_turn(self):
        for entry, expected in [(self.declaration(quote='This was never said.'), 'quote_not_found'),
                                (self.declaration(turn_id='T004'), 'quote_not_found'),
                                (self.declaration(turn_id='T999'), 'unverified')]:
            self.assertEqual(attribution.check(summary([entry]), self.turns)['checks'][0]['status'], expected)

    def test_plain_quotes_and_malformed_blocks(self):
        entry = self.declaration(responds_to=None)
        self.assertEqual(attribution.check(summary([entry]), self.turns)['checks'][0]['status'], 'quote_found')
        self.assertEqual(attribution.check('No block', self.turns)['status'], 'not_declared')
        self.assertEqual(attribution.check(summary([entry]) + '\n' + summary([entry]), self.turns)['status'], 'invalid')
        self.assertEqual(attribution.check(summary([[]]), self.turns)['checks'][0]['status'], 'unverified')

    def test_context_distinguishes_full_answers_from_older_check_snippets(self):
        self.assertIsNone(attribution.context(self.turns, 'initial', 0))
        self.assertEqual(attribution.context(self.turns[:3], 'review', 1)['full_answer_ids'], ['T001', 'T002'])
        self.assertEqual(attribution.context(self.turns, 'review', 2)['full_answer_ids'], ['T003', 'T004'])
        self.assertEqual(attribution.context(self.turns, 'summary', 1)['turns'][3]['full_answer_ids'], ['T001', 'T002'])
