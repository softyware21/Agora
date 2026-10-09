import json
from pathlib import Path
import tempfile
import unittest

import agora


class Participant:
    def __init__(self, stop=False):
        self.stop = stop
        self.calls = []

    def check(self):
        return 'subscription'

    def answer(self, prompt, timeout):
        data = json.loads(prompt.split('INPUT_JSON:\n')[1])
        self.calls.append(data)
        if self.stop and data['phase'] == 'review':
            raise agora.AgoraError('Test interruption')
        expected = '500' if data['phase'] == 'initial' else '501'
        declaration = [{'claim': 'Cost at 16.7 percent', 'expression': '3000 * 16.7 / 100',
                        'expected': expected, 'unit': 'USD'}]
        return 'A cost estimate.\n```agora-calculations\n' + json.dumps(declaration) + '\n```'


class CalculationFlowTests(unittest.TestCase):
    def test_both_reviewers_receive_same_checks_and_summary_is_checked(self):
        with tempfile.TemporaryDirectory() as path:
            providers = {name: Participant() for name in ['codex', 'claude']}
            result = agora.debate(providers, 'Question', 'Rules', 1, 30, Path(path))
            codex, claude = providers['codex'].calls, providers['claude'].calls
            self.assertNotIn('calculation_checks', codex[0])
            self.assertEqual(codex[1]['calculation_checks'], claude[1]['calculation_checks'])
            self.assertEqual(codex[1]['calculation_checks'][0]['checks'][0]['actual'], '501')
            self.assertEqual(codex[1]['calculation_checks'][0]['checks'][0]['status'], 'arithmetic_mismatch')
            self.assertEqual(len(codex[2]['calculation_checks']), 4)
            self.assertEqual(len(result['calculation_checks']), 5)
            self.assertEqual(result['calculation_checks'][-1]['checks'][0]['status'], 'arithmetic_match')
            report = (Path(path) / 'report.md').read_text(encoding='utf-8')
            self.assertIn('arithmetic_mismatch', report)
            self.assertIn('arithmetic_match', report)
            self.assertIn('remain unverified', report)

    def test_resume_recomputes_evidence_without_including_current_round(self):
        with tempfile.TemporaryDirectory() as path:
            folder = Path(path)
            with self.assertRaises(agora.AgoraError):
                agora.debate({'codex': Participant(), 'claude': Participant(stop=True)},
                             'Question', 'Rules', 1, 30, folder)
            file = folder / 'transcript.json'
            record = json.loads(file.read_text(encoding='utf-8'))
            record['calculation_checks'] = [{'status': 'fake_verified'}]
            file.write_text(json.dumps(record), encoding='utf-8')
            providers = {name: Participant() for name in ['codex', 'claude']}
            result = agora.debate(providers, 'Question', 'Rules', 1, 30, folder, resume=True)
            checks = providers['claude'].calls[0]['calculation_checks']
            self.assertEqual(len(checks), 2)
            self.assertTrue(all(item['phase'] == 'initial' for item in checks))
            self.assertEqual(checks[0]['checks'][0]['status'], 'arithmetic_mismatch')
            self.assertEqual(result['verification'], 'declared_arithmetic_only')
