import json
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

import agora
import run_state


class Participant:
    def __init__(self, name, stop_at=None):
        self.name = name
        self.stop_at = stop_at
        self.calls = []
        self.last_metadata = {'models': ['test-model']}

    def check(self):
        return 'subscription'

    def metadata(self):
        return {'cli_version': '1.2.3'}

    def answer(self, prompt, timeout):
        payload = json.loads(prompt.split('INPUT_JSON:\n')[1])
        self.calls.append(payload)
        if payload['phase'] == self.stop_at:
            raise agora.AgoraError('Limit reached.', 'usage_limit')
        return f'{self.name}: {payload["phase"]}'


class ResumeTests(unittest.TestCase):
    def participants(self, stop_name=None, phase=None):
        return {name: Participant(name, phase if name == stop_name else None)
                for name in ('codex', 'claude')}

    def stop(self, folder, name, phase):
        with self.assertRaises(agora.AgoraError):
            agora.debate(self.participants(name, phase), 'q', 'r', 1, 30, folder)
        return run_state.load(folder, agora.prompt_version())

    def test_resume_at_each_stage(self):
        cases = [('codex', 'initial', 5), ('claude', 'initial', 4),
                 ('codex', 'review', 3), ('claude', 'review', 2),
                 ('codex', 'summary', 1)]
        for name, phase, remaining in cases:
            with self.subTest(name=name, phase=phase), tempfile.TemporaryDirectory() as path:
                folder = Path(path)
                previous = self.stop(folder, name, phase)
                providers = self.participants()
                result = agora.debate(providers, 'q', 'r', 1, 30, folder, resume=True)
                self.assertEqual(sum(len(p.calls) for p in providers.values()), remaining)
                self.assertEqual(result['turns'][:len(previous['turns'])], previous['turns'])
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(result['attempts'][0]['stop_reason'], 'usage_limit')
                self.assertEqual(len(result['attempts']), 2)
                for provider in providers.values():
                    for call in provider.calls:
                        if call['phase'] == 'review':
                            peer = 'claude' if provider.name == 'codex' else 'codex'
                            self.assertEqual(call['peer_previous_answer'], f'{peer}: initial')

    def test_completed_run_is_unchanged_without_provider_calls(self):
        with tempfile.TemporaryDirectory() as path:
            folder = Path(path)
            agora.debate(self.participants(), 'q', 'r', 1, 30, folder)
            before = (folder / 'transcript.json').read_bytes()
            result = agora.debate({}, 'q', 'r', 1, 30, folder, resume=True)
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(before, (folder / 'transcript.json').read_bytes())

    def test_rejects_corruption_before_calls_or_writes(self):
        edits = [lambda r: r.update(schema_version=99),
                 lambda r: r.update(prompt_version='old'),
                 lambda r: r.update(question='changed'),
                 lambda r: r.update(status='completed'),
                 lambda r: r['turns'].reverse(),
                 lambda r: r['turns'].append(r['turns'][0]),
                 lambda r: r.update(attempts=None)]
        for edit in edits:
            with self.subTest(edit=edit), tempfile.TemporaryDirectory() as path:
                folder = Path(path)
                record = self.stop(folder, 'claude', 'review')
                edit(record)
                file = folder / 'transcript.json'
                file.write_text(json.dumps(record), encoding='utf-8')
                before = file.read_bytes()
                with self.assertRaises(agora.AgoraError):
                    agora.debate({}, 'q', 'r', 1, 30, folder, resume=True)
                self.assertEqual(before, file.read_bytes())

    def test_existing_run_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as path:
            folder = Path(path)
            self.stop(folder, 'claude', 'review')
            with self.assertRaisesRegex(agora.AgoraError, 'already exists'):
                agora.debate({}, 'q', 'r', 1, 30, folder)

    def test_only_one_writer_and_lock_released_on_error(self):
        with tempfile.TemporaryDirectory() as path:
            folder = Path(path)
            with self.assertRaisesRegex(ValueError, 'test failure'):
                with run_state.locked(folder):
                    with self.assertRaises(run_state.StateError):
                        with run_state.locked(folder):
                            self.fail('Second writer acquired the lock')
                    raise ValueError('test failure')
            with run_state.locked(folder):
                pass

    def test_attempt_and_model_metadata_saved(self):
        with tempfile.TemporaryDirectory() as path:
            record = agora.debate(self.participants(), 'q', 'r', 1, 30, Path(path))
            self.assertEqual(record['attempts'][0]['providers']['codex']['cli_version'], '1.2.3')
            self.assertEqual(record['turns'][0]['metadata']['models'], ['test-model'])

    def test_claude_quota_result_with_zero_exit_code(self):
        with patch.object(agora, 'executable', return_value='claude.exe'):
            provider = agora.Provider('claude', '.')
        response = json.dumps({'is_error': True, 'api_error_status': 429, 'result': 'Too many requests'})
        with patch.object(provider, 'check'), patch.object(agora, 'invoke', return_value=(0, response, '')):
            with self.assertRaises(agora.AgoraError) as error:
                provider.answer('test', 30)
            self.assertEqual(error.exception.reason, 'usage_limit')

    def test_cli_completed_resume_does_not_initialize_providers(self):
        with tempfile.TemporaryDirectory() as path:
            folder = Path(path)
            agora.debate(self.participants(), 'q', 'r', 1, 30, folder)
            with patch.object(sys, 'argv', ['agora', '--resume', path]), patch.object(agora, 'Provider') as provider:
                self.assertEqual(agora.main(), 0)
                provider.assert_not_called()

    def test_cli_resume_rejects_new_rules(self):
        with patch.object(sys, 'argv', ['agora', '--resume', 'unused', '--rules', 'changed']), patch.object(agora, 'Provider') as provider:
            self.assertEqual(agora.main(), 1)
            provider.assert_not_called()
