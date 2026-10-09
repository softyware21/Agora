import copy
import json
import unittest

import issues


def issue_text(status='disputed'):
    return '```agora-issues\n' + json.dumps([{
        'topic': 'Restart decision', 'status': status, 'reason': 'The positions differ.',
        'next_step': 'Obtain an authorized priority rule.',
        'positions': [{'turn_id': 'T003', 'position': 'Restart', 'quote': 'Restart is required.'},
                      {'turn_id': 'T004', 'position': 'Wait', 'quote': 'Do not restart yet.'}]}]) + '\n```'


class IssueTests(unittest.TestCase):
    def turns(self):
        return [{'provider': n, 'phase': phase, 'round': r, 'text': text} for n, phase, r, text in [
            ('codex', 'initial', 0, 'Initial answer A.'), ('claude', 'initial', 0, 'Initial answer B.'),
            ('codex', 'review', 1, 'Restart is required.'), ('claude', 'review', 1, 'Do not restart yet.'),
            ('codex', 'summary', 1, issue_text())]]

    def test_dispute_preserves_both_positions_and_needed_information(self):
        result = issues.ledger(self.turns())
        row = result['issues'][0]
        self.assertEqual(row['status'], 'disputed')
        self.assertEqual(row['citation_status'], 'quotes_found')
        self.assertEqual([p['position'] for p in row['positions']], ['Restart', 'Wait'])
        self.assertIn('disputed=1', issues.overview(result))

    def test_invalid_old_missing_and_duplicate_positions_do_not_become_agreement(self):
        for old, new in [('Restart is required.', 'Fabricated agreement.'), ('T003', 'T001'), ('T004', 'T003')]:
            turns = self.turns()
            turns[-1]['text'] = issue_text('agreed').replace(old, new)
            row = issues.ledger(turns)['issues'][0]
            self.assertEqual(row['status'], 'unverified')
            self.assertEqual(row['model_status'], 'agreed')

    def test_missing_block_and_empty_list_are_not_automatic_agreement(self):
        for text in ('No structured issues.', '```agora-issues\n[]\n```'):
            turns = self.turns()
            turns[-1]['text'] = text
            self.assertIn('unavailable', issues.overview(issues.ledger(turns)))

    def test_insufficient_information_is_distinct_and_semantic_status_is_not_verified(self):
        turns = self.turns()
        turns[-1]['text'] = issue_text('insufficient_information')
        self.assertEqual(issues.ledger(turns)['issues'][0]['status'], 'insufficient_information')
        # Quote presence alone cannot prove or disprove the model's consensus label.
        turns[-1]['text'] = issue_text('agreed')
        self.assertIn('Not factual verification', issues.overview(issues.ledger(turns)))

    def test_malformed_issue_keeps_result_unverified(self):
        turns = self.turns()
        turns[-1]['text'] = '```agora-issues\n[null]\n```'
        self.assertEqual(issues.ledger(turns)['issues'][0]['status'], 'unverified')
