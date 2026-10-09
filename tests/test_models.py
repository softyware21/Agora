import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agora
import continue_debate
import models
import run_state
from test_resume import Participant


class ModelTests(unittest.TestCase):
    def selection(self, **changes):
        return dict(models.validate(None), **changes)

    def providers(self, selection, stop=None):
        result = {n: Participant(n) for n in ('codex', 'claude')}
        for name, provider in result.items():
            provider.model = selection[name]
        name = selection['summary_provider']
        result['summary'] = Participant(name, stop)
        result['summary'].model = models.target(selection, name, 'summary')
        return result

    def test_factory_inherits_participant_model_for_summary(self):
        with patch.object(agora, 'executable', return_value='unused'):
            providers = agora.create_providers('.', self.selection(claude='opus', summary_provider='claude'))
        self.assertEqual(providers['summary'].name, 'claude')
        self.assertEqual(providers['summary'].model, 'opus')

    def test_claude_summary_uses_its_own_model_and_reports_both_names(self):
        selection = self.selection(codex='gpt-example', claude='sonnet', summary_provider='claude', summary_model='opus')
        providers = self.providers(selection)
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            record = agora.debate(providers, 'q', 'r', 1, 30, folder, model_selection=selection)
            self.assertEqual([len(p.calls) for p in providers.values()], [2, 2, 1])
            self.assertEqual(record['turns'][-1]['provider'], 'claude')
            self.assertEqual(record['turns'][-1]['metadata']['requested_model'], 'opus')
            self.assertEqual(record['turns'][-1]['metadata']['models'], ['test-model'])
            self.assertEqual(len(providers['summary'].calls[0]['debate_history']), 4)
            self.assertEqual(run_state.load(folder, agora.prompt_version())['model_selection'], selection)
            report = (folder / 'report.md').read_text(encoding='utf-8')
            self.assertIn('Requested model: opus; reported models: test-model', report)

    def test_changed_selection_cannot_resume_or_mutate_history(self):
        selection = self.selection(codex='gpt-example', summary_provider='claude')
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            with self.assertRaises(agora.AgoraError):
                agora.debate(self.providers(selection, 'summary'), 'q', 'r', 1, 30, folder, model_selection=selection)
            before = (folder / 'transcript.json').read_bytes()
            changed = dict(selection, codex='other-model')
            providers = self.providers(changed)
            with self.assertRaisesRegex(agora.AgoraError, 'Cannot change models'):
                agora.debate(providers, 'q', 'r', 1, 30, folder, resume=True, model_selection=changed)
            self.assertEqual((folder / 'transcript.json').read_bytes(), before)
            self.assertFalse(any(p.calls for p in providers.values()))
            providers = self.providers(selection)
            record = agora.debate(providers, 'q', 'r', 1, 30, folder, resume=True)
            self.assertEqual([len(p.calls) for p in providers.values()], [0, 0, 1])
            self.assertEqual(record['model_selection'], selection)

    def test_cli_resume_constructs_saved_models(self):
        selection = self.selection(codex='gpt-example', claude='sonnet', summary_model='gpt-summary')
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            with self.assertRaises(agora.AgoraError):
                agora.debate(self.providers(selection, 'summary'), 'q', 'r', 1, 30, folder, model_selection=selection)
            providers = self.providers(selection)
            with patch('sys.argv', ['agora.py', '--resume', str(folder)]), patch.object(agora, 'create_providers', return_value=providers) as factory:
                self.assertEqual(agora.main(), 0)
            self.assertEqual(factory.call_args.args[1], selection)
            self.assertEqual(sum(len(p.calls) for p in providers.values()), 1)

    def test_selection_tampering_fails_saved_hash(self):
        selection = self.selection(summary_provider='claude')
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            record = agora.debate(self.providers(selection), 'q', 'r', 1, 30, folder, model_selection=selection)
            record['model_selection']['claude'] = 'changed'
            (folder / 'transcript.json').write_text(json.dumps(record), encoding='utf-8')
            with self.assertRaisesRegex(run_state.StateError, 'Saved settings changed'):
                run_state.load(folder, agora.prompt_version())

    def test_continuation_inherits_or_changes_models_without_rewriting_parent(self):
        selection = self.selection(codex='gpt-original', summary_provider='claude', summary_model='opus')
        with tempfile.TemporaryDirectory() as root:
            parent = Path(root) / 'parent'
            agora.debate(self.providers(selection), 'q', 'r', 1, 30, parent, model_selection=selection)
            before = (parent / 'transcript.json').read_bytes()
            child = Path(root) / 'inherited'
            record = continue_debate.prepare(parent, child)
            self.assertEqual(record['model_selection'], selection)
            changed = self.selection(codex='gpt-new', summary_model='gpt-summary')
            child = Path(root) / 'changed'
            record = continue_debate.prepare(parent, child, model_selection=changed)
            providers = self.providers(changed)
            result = agora.debate(providers, 'q', 'r', 2, 30, child, resume=True)
            self.assertEqual(sum(len(p.calls) for p in providers.values()), 3)
            self.assertEqual(result['turns'][0]['metadata']['requested_model'], 'gpt-original')
            self.assertEqual(result['turns'][-1]['metadata']['requested_model'], 'gpt-summary')
            self.assertEqual(result['turns'][-1]['provider'], 'codex')
            self.assertEqual((parent / 'transcript.json').read_bytes(), before)
            run_state.load(child, agora.prompt_version())

    def test_plan_is_offline_and_counts_selected_summary_provider(self):
        import io
        output = io.StringIO()
        with patch('sys.argv', ['agora.py', '--rounds', '2', '--summary-provider', 'claude', '--plan']), patch('sys.stdout', output), patch.object(agora, 'create_providers') as factory, patch.object(agora.sources, 'collect') as collect:
            self.assertEqual(agora.main(), 0)
        factory.assert_not_called()
        collect.assert_not_called()
        self.assertIn('codex 3, claude 4', output.getvalue())

    def test_provider_change_clears_incompatible_summary_model(self):
        parser = argparse.ArgumentParser()
        models.add_arguments(parser)
        base = self.selection(summary_model='gpt-example')
        updated = models.from_args(parser.parse_args(['--summary-provider', 'claude']), base)
        self.assertIsNone(updated['summary_model'])
        updated = models.from_args(parser.parse_args(['--codex-model', 'default']), self.selection(codex='gpt-example'))
        self.assertIsNone(updated['codex'])

    def test_misconfigured_provider_fails_before_any_calls(self):
        selection = self.selection(codex='gpt-example')
        providers = self.providers(selection)
        providers['codex'].model = None
        with tempfile.TemporaryDirectory() as root, self.assertRaisesRegex(agora.AgoraError, 'does not match'):
            agora.debate(providers, 'q', 'r', 1, 30, Path(root), model_selection=selection)
        self.assertFalse(any(p.calls for p in providers.values()))
