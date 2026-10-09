import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agora


class ProviderModelTests(unittest.TestCase):
    def test_explicit_models_are_passed_as_single_cli_arguments(self):
        for name, model in [('codex', 'gpt-example'), ('claude', 'sonnet')]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                with patch.object(agora, 'executable', return_value=name):
                    provider = agora.Provider(name, folder, model)

                def invoke(args, cwd, timeout, prompt):
                    self.assertEqual(args[args.index('--model') + 1], model)
                    self.assertNotIn('--fallback-model', args)
                    if name == 'codex':
                        Path(args[args.index('-o') + 1]).write_text('Answer', encoding='utf-8')
                        self.assertIn('--ignore-user-config', args)
                        return 0, '', 'model: gpt-reported\n'
                    self.assertIn('--restricted', args)
                    return 0, json.dumps({'subtype': 'success', 'result': 'Answer', 'modelUsage': {'claude-reported': {}}}), ''

                with patch.object(provider, 'check'), patch.object(agora, 'invoke', side_effect=invoke):
                    self.assertEqual(provider.answer('Question', 30), 'Answer')
                self.assertEqual(provider.last_metadata['models'], [name.replace('codex', 'gpt') + '-reported'])

    def test_bad_model_values_fail_before_executable_lookup(self):
        for value in ('', '--other-flag', 'model with spaces', 'm\n--flag', 'x' * 129, 4):
            with self.subTest(value=value), patch.object(agora, 'executable') as lookup:
                with self.assertRaises(ValueError):
                    agora.Provider('codex', '.', value)
                lookup.assert_not_called()
