import hashlib
import json
import unittest

import source_evidence


def source():
    text = 'Example domains are reserved for documentation. This does not include all domains.'
    return {'id': 'S01', 'status': 'retrieved', 'text': text, 'url': 'https://example.org/',
            'final_url': 'https://example.org/', 'retrieved_at': '2026-10-09T00:00:00Z',
            'sha256': hashlib.sha256(text.encode()).hexdigest()}


def answer(quote='Example domains are reserved for documentation.', claim='All domains are reserved.'):
    return '```agora-sources\n' + json.dumps([{'claim': claim, 'source_id': 'S01',
        'quote': quote, 'relation': 'supports'}]) + '\n```'


class SourceEvidenceTests(unittest.TestCase):
    def test_real_quote_does_not_establish_claim_support(self):
        check = source_evidence.claims(answer(), 1, [source()])['checks'][0]
        self.assertEqual(check['status'], 'quote_found')
        self.assertIn('still needs review', check['reason'])
        self.assertIn('does not include all', check['context'])

    def test_fabricated_quote_is_not_found(self):
        check = source_evidence.claims(answer('All domain names are free to use.'), 1, [source()])['checks'][0]
        self.assertEqual(check['status'], 'quote_not_found')

    def test_unavailable_and_unknown_sources_stay_unverified(self):
        for snapshots in [[], [dict(source(), status='unavailable')]]:
            check = source_evidence.claims(answer(), 1, snapshots)['checks'][0]
            self.assertEqual(check['status'], 'unverified')

    def test_review_is_labeled_as_model_judgment(self):
        review = '```agora-source-reviews\n' + json.dumps([{
            'target': 'T001-S01', 'relation': 'contradicts',
            'reason': 'The quote concerns example domains, not all domains.'}]) + '\n```'
        turns = [{'text': answer(), 'provider': 'codex', 'phase': 'initial', 'round': 0},
                 {'text': review, 'provider': 'claude', 'phase': 'review', 'round': 1}]
        judgment = source_evidence.ledger(turns, [source()])[1]['assessments'][0]
        self.assertEqual(judgment['status'], 'model_assessment')
        self.assertEqual(judgment['relation'], 'contradicts')
        turns[0]['text'] = answer('Invented quote which does not appear.')
        self.assertEqual(source_evidence.ledger(turns, [source()])[1]['assessments'][0]['status'], 'unverified')

    def test_invalid_and_missing_blocks(self):
        for text, expected in [('No citations.', 'not_declared'),
                               ('```agora-sources\nnot json\n```', 'invalid')]:
            self.assertEqual(source_evidence.claims(text, 1, [])['status'], expected)
