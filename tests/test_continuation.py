import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agora
import continue_debate as continuation
import run_state
from test_resume import Participant
from test_source_evidence import source, answer


class ContinuationTests(unittest.TestCase):
    def providers(self, stop=None):
        return {n: Participant(n, 'review' if n == stop else None) for n in ('codex', 'claude')}

    def parent(self, root, rounds=1):
        path = Path(root) / 'parent'
        agora.debate(self.providers(), 'Original question', 'Original rules', rounds, 30, path)
        return path

    def run_child(self, path, record, providers):
        return agora.debate(providers, record['question'], record['rules'], record['rounds'], 30, path, resume=True)

    def test_add_round_uses_three_calls_and_preserves_parent_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            parent = self.parent(root)
            before = (parent / 'transcript.json').read_bytes()
            child = Path(root) / 'child'
            record = continuation.prepare(parent, child, note='New priority: minimize downtime.', rules='Updated rules')
            providers = self.providers()
            result = self.run_child(child, record, providers)
            self.assertEqual(sum(len(p.calls) for p in providers.values()), 3)
            self.assertEqual((parent / 'transcript.json').read_bytes(), before)
            self.assertEqual((child / 'parent.json').read_bytes(), before)
            a, b = providers['codex'].calls[0], providers['claude'].calls[0]
            self.assertEqual(a['turn_context'], b['turn_context'])
            self.assertEqual(a['peer_previous_answer'], 'claude: review')
            self.assertEqual(a['continuation_context']['previous_rules'], 'Original rules')
            self.assertEqual(a['rules'], 'Updated rules')
            self.assertEqual(result['status'], 'completed')

    def test_interrupted_continuation_resumes_without_repeating_completed_review(self):
        with tempfile.TemporaryDirectory() as root:
            parent = self.parent(root)
            child = Path(root) / 'child'
            record = continuation.prepare(parent, child)
            with self.assertRaises(agora.AgoraError):
                self.run_child(child, record, self.providers('claude'))
            providers = self.providers()
            self.run_child(child, record, providers)
            self.assertEqual(sum(len(p.calls) for p in providers.values()), 2)
            self.assertEqual(providers['claude'].calls[0]['turn_context']['full_answer_ids'], ['T003', 'T004'])

    def test_multiple_extensions_keep_supplements_and_pass_three_original_round_limit(self):
        with tempfile.TemporaryDirectory() as root:
            parent = self.parent(root, rounds=3)
            child = Path(root) / 'child'
            record = continuation.prepare(parent, child, note='First new fact.')
            self.run_child(child, record, self.providers())
            grandchild = Path(root) / 'grandchild'
            record = continuation.prepare(child, grandchild, note='Second new fact.')
            providers = self.providers()
            self.run_child(grandchild, record, providers)
            self.assertEqual(record['rounds'], 5)
            self.assertEqual([x['text'] for x in providers['codex'].calls[0]['continuation_context']['supplements']],
                             ['First new fact.', 'Second new fact.'])

    def test_added_source_does_not_retroactively_validate_old_claim(self):
        class Claimant(Participant):
            def answer(self, prompt, timeout):
                super().answer(prompt, timeout)
                return answer()
        with tempfile.TemporaryDirectory() as root:
            parent = Path(root) / 'parent'
            agora.debate({n: Claimant(n) for n in ('codex', 'claude')}, 'q', 'r', 1, 30, parent)
            with patch.object(continuation.sources, 'collect', return_value=[source()]):
                record = continuation.prepare(parent, Path(root) / 'child', urls=['https://example.org/'])
            self.assertEqual(record['source_checks'][0]['checks'][0]['status'], 'unverified')
            self.assertEqual(record['turns'][0]['source_ids'], [])
            providers = self.providers()
            self.run_child(Path(root) / 'child', record, providers)
            self.assertEqual(providers['codex'].calls[0]['sources'][0]['id'], 'S01')

    def test_parent_or_inherited_turn_tampering_is_rejected(self):
        for target in ('parent', 'turn'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as root:
                parent = self.parent(root)
                child = Path(root) / 'child'
                record = continuation.prepare(parent, child)
                if target == 'parent':
                    (child / 'parent.json').write_text('{}')
                else:
                    record['turns'][0]['text'] = 'Altered answer'
                    (child / 'transcript.json').write_text(json.dumps(record))
                with self.assertRaises(run_state.StateError):
                    run_state.load(child, agora.prompt_version())

    def test_preview_is_offline_and_creates_no_child(self):
        with tempfile.TemporaryDirectory() as root:
            parent = self.parent(root)
            with patch('sys.argv', ['continue_debate.py', '--from', str(parent), '--plan']), \
                    patch.object(agora, 'Provider', side_effect=AssertionError('No model')), \
                    patch.object(continuation.sources, 'collect', side_effect=AssertionError('No network')):
                self.assertEqual(continuation.main(), 0)
            self.assertEqual([p.name for p in Path(root).iterdir()], ['parent'])

    def test_incomplete_or_single_model_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            parent = self.parent(root)
            path = parent / 'transcript.json'
            record = json.loads(path.read_text())
            record['turns'][1]['metadata']['actual_provider'] = 'codex'
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'Single-model'):
                continuation.prepare(parent, Path(root) / 'child')
            record['status'] = 'stopped'
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                continuation.prepare(parent, Path(root) / 'child')
