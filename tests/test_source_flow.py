import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agora
from test_source_evidence import source, answer


class Participant:
    def __init__(self, stop=False):
        self.calls = []
        self.stop = stop

    def check(self):
        return 'subscription'

    def answer(self, prompt, timeout):
        data = json.loads(prompt.split('INPUT_JSON:\n')[1])
        self.calls.append(data)
        if self.stop and data['phase'] == 'review':
            raise agora.AgoraError('Test interruption')
        text = answer()
        if data['phase'] != 'initial':
            text += '\n```agora-source-reviews\n' + json.dumps([{
                'target': 'T001-S01', 'relation': 'contradicts',
                'reason': 'The source reserves example domains, not every domain.'}]) + '\n```'
        return text


class SourceFlowTests(unittest.TestCase):
    def test_shared_sources_and_prior_round_checks(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(agora.sources, 'collect', return_value=[source()]):
            providers = {name: Participant() for name in ('codex', 'claude')}
            record = agora.debate(providers, 'q', 'r', 1, 30, Path(folder), source_urls=['https://example.org/'])
            codex, claude = providers['codex'].calls, providers['claude'].calls
            self.assertEqual(codex[0]['sources'], claude[0]['sources'])
            self.assertEqual(codex[1]['source_checks'], claude[1]['source_checks'])
            self.assertEqual(record['source_checks'][2]['assessments'][0]['relation'], 'contradicts')
            report = (Path(folder) / 'report.md').read_text(encoding='utf-8')
            self.assertIn('quote_found', report)
            self.assertIn('model_assessment', report)

    def test_resume_reuses_snapshot_and_rejects_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            with patch.object(agora.sources, 'collect', return_value=[source()]), self.assertRaises(agora.AgoraError):
                agora.debate({'codex': Participant(), 'claude': Participant(True)}, 'q', 'r', 1, 30, path,
                             source_urls=['https://example.org/'])
            with patch.object(agora.sources, 'collect') as collect:
                record = agora.debate({'codex': Participant(), 'claude': Participant()}, 'q', 'r', 1, 30,
                                      path, resume=True)
                collect.assert_not_called()
            record['sources'][0]['text'] = 'Changed text.'
            file = path / 'transcript.json'
            file.write_text(json.dumps(record), encoding='utf-8')
            with self.assertRaises(agora.AgoraError):
                agora.debate({}, 'q', 'r', 1, 30, path, resume=True)

    def test_unavailable_source_never_gets_quote_match(self):
        snapshot = dict(source(), status='unavailable', text='', error='HTTP 404')
        with tempfile.TemporaryDirectory() as folder, patch.object(agora.sources, 'collect', return_value=[snapshot]):
            result = agora.debate({'codex': Participant(), 'claude': Participant()}, 'q', 'r', 1, 30,
                                  Path(folder), source_urls=['https://example.org/'])
            self.assertEqual(result['source_checks'][0]['checks'][0]['status'], 'unverified')
            self.assertEqual(result['source_checks'][2]['assessments'][0]['status'], 'unverified')
