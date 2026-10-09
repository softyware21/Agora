import json
from pathlib import Path
import tempfile
import unittest

import agora
from test_attribution import summary


class Participant:
    def __init__(self, stop=False):
        self.calls = []
        self.stop = stop

    def check(self):
        return 'subscription'

    def answer(self, prompt, timeout):
        data = json.loads(prompt.split('INPUT_JSON:\n')[1])
        self.calls.append(data)
        if data['phase'] == 'initial':
            return 'Initial conclusion.'
        if data['phase'] == 'review':
            if self.stop:
                raise agora.AgoraError('Stopped for test')
            return 'I agree with the initial conclusion.'
        return summary([{'claim': 'A accepted B\'s new review qualification.', 'turn_id': 'T003',
                         'quote': 'I agree with the initial conclusion.', 'responds_to': 'T004'}])


class AttributionFlowTests(unittest.TestCase):
    def test_false_same_round_acceptance_is_visible_in_saved_report(self):
        with tempfile.TemporaryDirectory() as folder:
            providers = {n: Participant() for n in ('codex', 'claude')}
            record = agora.debate(providers, 'q', 'r', 1, 30, Path(folder))
            a, b = providers['codex'].calls, providers['claude'].calls
            self.assertNotIn('turn_context', a[0])
            self.assertEqual(a[1]['turn_context'], b[1]['turn_context'])
            self.assertEqual(a[2]['turn_context']['turns'][2]['full_answer_ids'], ['T001', 'T002'])
            self.assertEqual(record['attribution_checks'][0]['checks'][0]['status'], 'context_not_available')
            self.assertIn('context_not_available', (Path(folder) / 'report.md').read_text())

    def test_resume_preserves_context_without_exposing_completed_peer_review(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            with self.assertRaises(agora.AgoraError):
                agora.debate({'codex': Participant(), 'claude': Participant(True)}, 'q', 'r', 1, 30, path)
            providers = {n: Participant() for n in ('codex', 'claude')}
            agora.debate(providers, 'q', 'r', 1, 30, path, resume=True)
            context = providers['claude'].calls[0]['turn_context']
            self.assertEqual(context['full_answer_ids'], ['T001', 'T002'])
            self.assertEqual([t['id'] for t in context['turns']], ['T001', 'T002'])
            self.assertEqual(len(providers['codex'].calls), 1)
