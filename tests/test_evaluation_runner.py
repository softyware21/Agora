import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agora
import evaluate
import evaluation
from test_evaluation import answer


class Participant:
    def __init__(self, name, stop=False):
        self.name = name
        self.stop = stop
        self.calls = []

    def check(self):
        return 'subscription'

    def metadata(self):
        return {'cli_version': 'test-version'}

    def answer(self, prompt, timeout):
        data = json.loads(prompt.split('INPUT_JSON:\n')[1])
        self.calls.append(data)
        if self.stop and data['phase'] == 'review':
            raise agora.AgoraError('Usage limit reached.', 'usage_limit')
        case = next(c for c in evaluation.load_cases() if c['question'] == data['question'])
        if self.name == 'claude' and data['phase'] == 'initial':
            return 'No structured answer.'
        return answer(case['expected'])


class EvaluationRunnerTests(unittest.TestCase):
    def providers(self, stop=False):
        return {n: Participant(n, stop and n == 'claude') for n in ('codex', 'claude')}

    def batch(self, root):
        folder = Path(root) / 'batch'
        evaluate.create_batch(folder, evaluation.load_cases()[:2], 1)
        return folder

    def test_shared_initial_context_and_paired_totals(self):
        with tempfile.TemporaryDirectory() as root:
            folder = self.batch(root)
            providers = self.providers()
            evaluate.run_batch(folder, providers)
            scores = json.loads((folder / 'scores.json').read_text())
            self.assertEqual(scores['paired_cases'], 2)
            self.assertEqual(scores['passes'], {'codex': 2, 'claude': 0, 'debate': 2})
            self.assertEqual(scores['transitions']['claude'], {'improved': 2, 'regressed': 0})
            self.assertEqual(sum(len(p.calls) for p in providers.values()), 10)
            self.assertEqual(providers['codex'].calls[0], providers['claude'].calls[0])
            self.assertNotIn('expected', providers['codex'].calls[0])
            self.assertNotIn('rationale', providers['codex'].calls[0])
            self.assertIn('not an equal-budget comparison', (folder / 'comparison.md').read_text())

    def test_partial_batch_is_visible_and_resume_only_calls_missing_turns(self):
        with tempfile.TemporaryDirectory() as root:
            folder = self.batch(root)
            with self.assertRaises(agora.AgoraError):
                evaluate.run_batch(folder, self.providers(stop=True))
            scores = json.loads((folder / 'scores.json').read_text())
            self.assertEqual(scores['paired_cases'], 0)
            self.assertEqual(scores['cases'][0]['scores']['debate']['status'], 'pending')
            self.assertEqual(scores['cases'][1]['status'], 'not_started')
            first = json.loads((folder / 'compound-change/transcript.json').read_text())['turns']
            providers = self.providers()
            evaluate.run_batch(folder, providers)
            self.assertEqual(sum(len(p.calls) for p in providers.values()), 7)
            final = json.loads((folder / 'compound-change/transcript.json').read_text())['turns']
            self.assertEqual(first, final[:len(first)])

    def test_completed_batch_requires_no_providers(self):
        with tempfile.TemporaryDirectory() as root:
            folder = self.batch(root)
            evaluate.run_batch(folder, self.providers())
            before = (folder / 'compound-change/transcript.json').read_bytes()
            evaluate.run_batch(folder, {})
            self.assertEqual(before, (folder / 'compound-change/transcript.json').read_bytes())
            with patch('sys.argv', ['evaluate.py', '--resume', str(folder)]), \
                    patch.object(agora, 'Provider', side_effect=AssertionError('Must stay offline')):
                self.assertEqual(evaluate.main(), 0)

    def test_changed_manifest_rejected_before_calls(self):
        with tempfile.TemporaryDirectory() as root:
            folder = self.batch(root)
            path = folder / 'evaluation.json'
            data = json.loads(path.read_text())
            data['cases'][0]['expected']['final_price'] = '100'
            path.write_text(json.dumps(data))
            providers = self.providers()
            with self.assertRaisesRegex(ValueError, 'settings changed'):
                evaluate.run_batch(folder, providers)
            self.assertFalse(any(p.calls for p in providers.values()))

    def test_valid_but_unrelated_transcript_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            folder = self.batch(root)
            providers = self.providers()
            case = evaluation.load_cases()[1]
            agora.debate(providers, case['question'], evaluation.rules(case), 1, 30, folder / 'compound-change')
            with self.assertRaisesRegex(ValueError, 'does not belong'):
                evaluate.run_batch(folder, {})

    def test_offline_listing_report_and_unknown_case(self):
        with patch.object(agora, 'Provider', side_effect=AssertionError('Must stay offline')):
            with patch('sys.argv', ['evaluate.py']):
                self.assertEqual(evaluate.main(), 0)
            with patch('sys.argv', ['evaluate.py', '--case', 'unknown']):
                self.assertEqual(evaluate.main(), 1)
            with tempfile.TemporaryDirectory() as root:
                folder = self.batch(root)
                with patch('sys.argv', ['evaluate.py', '--report', str(folder)]):
                    self.assertEqual(evaluate.main(), 0)
                scores = json.loads((folder / 'scores.json').read_text())
                self.assertEqual(scores['paired_cases'], 0)

    def test_existing_batch_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            folder = self.batch(root)
            with self.assertRaises(FileExistsError):
                evaluate.create_batch(folder, evaluation.load_cases(), 1)
