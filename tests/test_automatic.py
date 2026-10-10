import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agora
import automatic
from local_app import App
import models
from test_resume import Participant


class AutomaticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.status = 'disputed'
        self.repeat = False
        self.calls = []
        self.fail = False
        self.app = App(self.root, self.factory)

    def tearDown(self):
        if self.app.thread:
            self.app.stop()
            self.app.thread.join(5)
        self.temp.cleanup()

    def factory(self, cwd, selection):
        selection = models.validate(selection)
        owner = self

        class Fake(Participant):
            def answer(self, prompt, timeout):
                data = json.loads(prompt.split('INPUT_JSON:\n')[1])
                owner.calls.append(data['phase'])
                if owner.fail and data['phase'] == 'review':
                    raise agora.AgoraError('Fixture stop', 'usage_limit')
                if data['phase'] != 'summary':
                    return self.name + ': a sufficiently long position for citation'
                history = data['debate_history']
                positions = [{'turn_id': f'T{i + 1:03d}', 'position': str(0 if owner.repeat else len(history)) + turn['provider'],
                              'quote': turn['text']} for i, turn in enumerate(history) if i >= len(history) - 2]
                if owner.status == 'missing':
                    return 'No issue assessment.'
                return 'A conditional recommendation.\n```agora-issues\n' + json.dumps([{
                    'topic': 'Choose a trial length', 'status': owner.status, 'reason': 'The trial needs comparison.',
                    'next_step': 'Compare the assumptions.', 'positions': positions}]) + '\n```'

        providers = {name: Fake(name) for name in ('codex', 'claude')}
        for name, provider in providers.items():
            provider.model = selection[name]
        name = selection['summary_provider']
        providers['summary'] = Fake(name)
        providers['summary'].model = models.target(selection, name, 'summary')
        return providers

    def run_job(self, **kwargs):
        result = self.app.start(dict(question='Synthetic decision', automatic=True, rounds=3, **kwargs))
        self.app.thread.join(5)
        self.assertFalse(self.app.thread.is_alive())
        return result['run_id'], self.app.state()['run_id']

    def test_preview_counts_each_intermediate_summary(self):
        plan = self.app.plan(dict(question='q', automatic=True, rounds=3))
        self.assertEqual(plan['calls'], 11)
        self.assertEqual(plan['by_provider'], {'codex': 7, 'claude': 4})
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertFalse(self.calls)
        with self.assertRaises(ValueError):
            self.app.plan(dict(question='q', automatic='yes'))

    def test_stops_at_limit_and_preserves_parent_summaries(self):
        first, last = self.run_job()
        self.assertNotEqual(first, last)
        self.assertEqual(len(self.calls), 11)
        self.assertEqual(self.app.detail(last)['automatic']['reason'], 'round_limit')
        self.assertEqual(self.app.record(last)['rounds'], 3)
        self.assertEqual(self.app.record(first)['rounds'], 1)
        self.assertEqual([item['id'] for item in self.app.history()], [last])
        self.assertIsNotNone(self.app.detail(last)['previous_run'])
        parent = json.loads((self.root / last / 'parent.json').read_text())
        self.assertEqual(parent['status'], 'completed')
        self.assertTrue(parent['summary'])

    def test_early_stops_do_not_spend_the_remaining_budget(self):
        for status, reason in [('agreed', 'agreement'), ('insufficient_information', 'needs_information'),
                               ('missing', 'assessment_unavailable')]:
            self.status = status
            self.calls.clear()
            first, last = self.run_job()
            self.assertEqual(first, last)
            self.assertEqual(len(self.calls), 5)
            self.assertEqual(self.app.detail(last)['automatic']['reason'], reason)

    def test_identical_reported_positions_stop_after_second_round(self):
        self.repeat = True
        _, last = self.run_job()
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(self.app.detail(last)['automatic']['reason'], 'repeated_positions')

    def test_resume_keeps_original_automatic_round_budget(self):
        self.fail = True
        first, last = self.run_job()
        self.assertEqual(first, last)
        self.assertEqual(self.app.state()['status'], 'stopped')
        self.assertEqual(self.app.plan({'mode': 'resume', 'parent': first})['calls'], 9)
        self.fail = False
        self.calls.clear()
        self.app = App(self.root, self.factory)
        self.app.start({'mode': 'resume', 'parent': first})
        self.app.thread.join(5)
        self.assertEqual(self.app.state()['status'], 'completed')
        self.assertEqual(len(self.calls), 9)
        self.assertEqual(self.app.detail(self.app.state()['run_id'])['automatic']['reason'], 'round_limit')

    def test_stop_during_summary_prevents_another_round(self):
        factory = self.factory
        def stopping(cwd, selection):
            providers = factory(cwd, selection)
            answer = providers['summary'].answer
            def stop(prompt, timeout):
                result = answer(prompt, timeout)
                self.app.stop()
                return result
            providers['summary'].answer = stop
            return providers
        self.app.factory = stopping
        _, last = self.run_job()
        self.assertEqual(len(self.calls), 5)
        self.assertEqual(self.app.detail(last)['automatic']['reason'], 'user_stop')

    def test_time_budget_is_shared_across_rounds(self):
        original = agora.debate
        limits = []
        clock = [0]
        def debate(*args, **kwargs):
            limits.append(kwargs['deadline_seconds'])
            result = original(*args, **kwargs)
            clock[0] += 350
            return result
        with patch('local_app.time.monotonic', side_effect=lambda: clock[0]), patch('agora.debate', side_effect=debate):
            _, last = self.run_job()
        self.assertEqual(limits, [600, 250])
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(self.app.detail(last)['automatic']['reason'], 'deadline')

    def test_corrupt_automatic_policy_is_rejected(self):
        (self.root / 'automatic.json').write_text('{"target_round":100,"reason":"running"}')
        with self.assertRaises(ValueError):
            automatic.load(self.root)
