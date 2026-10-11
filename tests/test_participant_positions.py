import json
import unittest

import automatic
import issues


def answer(provider, disposition='ready', **changes):
    value = dict(disposition=disposition, conclusion='A synthetic conclusion.', conditions=['Within the stated premise.'])
    value.update(changes)
    return dict(provider=provider, phase='review', round=1,
                text='```agora-position\n' + json.dumps([value]) + '\n```')


class ParticipantPositionTests(unittest.TestCase):
    def test_latest_answer_wins_and_summary_cannot_supply_positions(self):
        turns = [answer('codex'), answer('claude'), answer('codex', 'blocked')]
        turns.append(dict(answer('claude', 'blocked'), phase='summary'))
        board = issues.participant_positions(turns)
        self.assertEqual(board['status'], 'different_categories')
        self.assertEqual([p['turn_id'] for p in board['positions']], ['T003', 'T002'])

    def test_missing_latest_declaration_does_not_reuse_an_old_one(self):
        turns = [answer('codex'), answer('claude'), dict(provider='codex', phase='review', text='No declaration.')]
        board = issues.participant_positions(turns)
        self.assertEqual(board['status'], 'unavailable')
        self.assertEqual(board['positions'][0]['status'], 'unavailable')

    def test_duplicate_or_malformed_declarations_are_unavailable(self):
        original = answer('codex')['text']
        for text in [original + '\n' + original, '```agora-position\n[null]\n```',
                     original.replace('"disposition": "ready"', '"disposition":"ready","disposition":"blocked"')]:
            self.assertEqual(issues.participant_positions([dict(answer('codex'), text=text), answer('claude')])['status'], 'unavailable')
        for changes in [dict(disposition='verified'), dict(conclusion=''), dict(conditions=[]),
                        dict(conditions=['x' * 501]), dict(extra='hidden condition')]:
            self.assertEqual(issues.participant_positions([answer('codex', **changes), answer('claude')])['status'], 'unavailable')

    def test_same_category_is_not_semantic_agreement(self):
        board = issues.participant_positions([answer('codex', conclusion='Choose A.'), answer('claude', conclusion='Choose B.')])
        self.assertEqual(board['status'], 'same_category')
        self.assertEqual([p['conclusion'] for p in board['positions']], ['Choose A.', 'Choose B.'])

    def test_false_summary_consensus_uses_direct_answers_not_cached_positions(self):
        record = {'rounds': 1, 'turns': [answer('codex'), answer('claude', 'blocked')],
                  'issue_outcomes': {'status': 'parsed', 'issues': [{'status': 'agreed'}]},
                  'participant_positions': {'status': 'same_category'}}
        self.assertEqual(automatic.assess(record, {'target_round': 2})[0], 'participant_positions_differ')
        record['turns'][1] = answer('claude')
        self.assertEqual(automatic.assess(record, {'target_round': 2})[0], 'consensus_unverified')

    def test_legacy_answers_remain_unavailable_not_agreed(self):
        self.assertEqual(issues.participant_positions([]), {'status': 'unavailable', 'positions': []})
