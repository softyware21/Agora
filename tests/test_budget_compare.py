from fractions import Fraction
from itertools import product
import json
from pathlib import Path
import tempfile
import unittest

import agora
import budget_compare as budget
import evaluation
from test_evaluation import answer


class Participant:
    def __init__(self, name, stop_at=None):
        self.name, self.stop_at = name, stop_at
        self.calls = []
        self.last_metadata = {'models': ['test']}

    def check(self):
        return 'subscription'

    def metadata(self):
        return {'cli_version': 'test'}

    def answer(self, prompt, timeout):
        data = json.loads(prompt.split('INPUT_JSON:\n')[1])
        self.calls.append(data)
        if len(self.calls) == self.stop_at:
            raise agora.AgoraError('Stopped', 'usage_limit')
        case = evaluation.load_cases('challenge')[0]
        return self.name + '\n' + answer(case['expected'])


class BudgetTests(unittest.TestCase):
    def test_challenge_keys_have_independent_derivations(self):
        cases = {c['id']: c for c in evaluation.load_cases('challenge')}
        e = cases['reversed-aggregate']['expected']
        self.assertEqual(Fraction(e['a_percent']), Fraction(81 + 2, 90 + 10) * 100)
        self.assertEqual(Fraction(e['b_percent']), Fraction(9 + 18, 10 + 90) * 100)
        self.assertEqual(Fraction(81, 90), Fraction(9, 10))
        self.assertEqual(Fraction(2, 10), Fraction(18, 90))
        event_positive = Fraction(1, 100) * Fraction(9, 10)
        not_event_positive = Fraction(99, 100) * Fraction(1, 20)
        self.assertEqual(Fraction(cases['dependent-alerts']['expected']['posterior']),
                         event_positive / (event_positive + not_event_positive))
        feasible = []
        for bits in product((0, 1), repeat=5):
            cost = sum(x * y for x, y in zip(bits, (6, 4, 5, 3, 2)))
            value = sum(x * y for x, y in zip(bits, (13, 8, 12, 9, 4)))
            if cost <= 10 and (not bits[3] or bits[1]) and not (bits[0] and bits[2]):
                feasible.append((value, -cost, ''.join(c for c, b in zip('ABCDE', bits) if b)))
        value, neg_cost, projects = max(feasible)
        key = cases['conditional-projects']['expected']
        self.assertEqual((str(value), str(-neg_cost), projects), (key['return'], key['cost'], key['projects']))
        self.assertFalse(any(delete and not delete for delete in (True, False)))
        self.assertEqual(cases['inconsistent-policy']['expected']['action'], 'no_valid_action')

    def test_equal_calls_routing_and_context_isolation(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'batch'
            budget.create(folder, evaluation.load_cases('challenge')[:1])
            providers = {n: Participant(n) for n in ('codex', 'claude')}
            budget.run(folder, providers)
            self.assertEqual([len(providers[n].calls) for n in ('codex', 'claude')], [8, 7])
            for arm in budget.ARMS:
                record = json.loads((folder / arm / 'reversed-aggregate/transcript.json').read_text())
                self.assertEqual(len(record['turns']), 5)
                actual = [t['metadata']['actual_provider'] for t in record['turns']]
                expected = ['codex', 'claude', 'codex', 'claude', 'codex'] if arm == 'mixed' else [arm[:-5]] * 5
                self.assertEqual(actual, expected)
            # Codex-only starts after its three mixed-arm calls, with fresh initial context.
            self.assertNotIn('peer_previous_answer', providers['codex'].calls[3])
            self.assertEqual(providers['claude'].calls[2]['execution_context']['participants'],
                             {'participant_A': 'claude', 'participant_B': 'claude'})
            self.assertEqual(providers['claude'].calls[-1]['debate_history'][0]['provider'], 'participant_A')
            self.assertTrue(providers['codex'].calls[5]['peer_previous_answer'].startswith('codex'))
            self.assertTrue(providers['claude'].calls[4]['peer_previous_answer'].startswith('claude'))
            scores = json.loads((folder / 'scores.json').read_text())
            self.assertEqual(scores['paired_cases'], 1)
            self.assertEqual(scores['passes'], {a: 1 for a in budget.ARMS})
            budget.run(folder, {})

    def test_incorrect_provider_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'batch'
            budget.create(folder, evaluation.load_cases('challenge')[:1])
            budget.run(folder, {n: Participant(n) for n in ('codex', 'claude')})
            path = folder / 'claude-only/reversed-aggregate/transcript.json'
            record = json.loads(path.read_text())
            record['turns'][-1]['metadata']['actual_provider'] = 'codex'
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'routing'):
                budget.run(folder, {})

    def test_resume_preserves_completed_arms_and_excludes_partial_pairs(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'batch'
            budget.create(folder, evaluation.load_cases('challenge')[:1])
            providers = {'codex': Participant('codex', stop_at=5), 'claude': Participant('claude')}
            with self.assertRaises(agora.AgoraError):
                budget.run(folder, providers)
            self.assertEqual(json.loads((folder / 'scores.json').read_text())['paired_cases'], 0)
            fresh = {n: Participant(n) for n in ('codex', 'claude')}
            budget.run(folder, fresh)
            self.assertEqual(sum(len(p.calls) for p in fresh.values()), 9)
            self.assertEqual(json.loads((folder / 'scores.json').read_text())['paired_cases'], 1)

    def test_changed_arm_rejected_before_calls(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'batch'
            budget.create(folder, evaluation.load_cases('challenge')[:1])
            path = folder / 'claude-only/evaluation.json'
            config = json.loads(path.read_text())
            config['rounds'] = 2
            path.write_text(json.dumps(config))
            providers = {n: Participant(n) for n in ('codex', 'claude')}
            with self.assertRaises(ValueError):
                budget.run(folder, providers)
            self.assertFalse(any(p.calls for p in providers.values()))
