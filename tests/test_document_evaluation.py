import copy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

import agora
import budget_compare as budget
import evaluate
import evaluation
from test_budget_compare import Participant
from test_evaluation import answer


class DocumentEvaluationTests(unittest.TestCase):
    def test_documents_are_identical_and_keys_are_withheld(self):
        case = evaluation.load_cases('documents')[0]
        prompt = evaluation.question(case)
        self.assertEqual(json.loads(prompt.split('DOCUMENTS_JSON:\n')[1]), case['documents'])
        changed = copy.deepcopy(case)
        changed['expected']['days'] = '999'
        changed['rationale'] = 'HIDDEN_RATIONALE'
        self.assertEqual(prompt, evaluation.question(changed))
        self.assertEqual(evaluation.rules(case), evaluation.rules(changed))

    def test_answer_requires_both_correct_value_and_source(self):
        case = evaluation.load_cases('documents')[0]
        self.assertTrue(date(2026, 4, 1) <= date(2026, 4, 15) <= date(2026, 6, 30))
        self.assertLess(date(2026, 4, 15), date(2026, 5, 1))
        self.assertEqual(evaluation.grade(answer(case['expected']), case)['status'], 'pass')
        incorrect = dict(case['expected'], governing_document='D3')
        self.assertEqual(evaluation.grade(answer(incorrect), case)['status'], 'fail')

    def test_conflict_and_incompatible_denominators_do_not_receive_numeric_credit(self):
        conflict, metrics = evaluation.load_cases('documents')[1:]
        self.assertEqual(evaluation.grade(answer(dict(conflict['expected'], action='restart')), conflict)['status'], 'fail')
        self.assertEqual(evaluation.grade(answer(dict(metrics['expected'], february_request_percent='0.8')), metrics)['status'], 'fail')
        for case in (conflict, metrics):
            self.assertEqual(evaluation.grade(answer(case['expected']), case)['status'], 'pass')

    def test_invalid_documents_are_rejected(self):
        case = evaluation.load_cases('documents')[0]
        for documents in ([], [{'id': 'D1', 'text': 'x' * 2001}], [case['documents'][0]] * 2):
            changed = dict(case, documents=documents)
            with self.assertRaises(ValueError):
                evaluation.validate_cases([changed])

    def test_structured_roles_are_neutral_without_rewriting_evidence(self):
        provider = Participant('claude')
        wrapper = budget.RoutedProvider(provider, 'claude', 'codex', 'claude-only')
        history = [{'provider': 'codex', 'text': 'The document literally says codex.'}]
        wrapper.answer(agora.build_prompt('q', 'r', 'summary', history=history), 30)
        data = provider.calls[0]
        self.assertEqual(data['debate_history'][0]['provider'], 'participant_A')
        self.assertEqual(data['debate_history'][0]['text'], history[0]['text'])
        self.assertEqual(data['execution_context']['participants'], {'participant_A': 'claude', 'participant_B': 'claude'})
        self.assertTrue(data['execution_context']['same_provider'])
        self.assertEqual(agora.speaker({'provider': 'codex', 'metadata': wrapper.last_metadata}), 'participant_A (claude)')

    def test_legacy_partial_batch_cannot_mix_prompt_versions(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'batch'
            budget.create(folder, evaluation.load_cases('challenge')[:1])
            path = folder / 'comparison.json'
            config = json.loads(path.read_text())
            config['version'] = 1
            config['fingerprint'] = evaluate.digest({k: v for k, v in config.items() if k != 'fingerprint'})
            evaluate.write_json(path, config)
            with self.assertRaisesRegex(ValueError, 'Routing prompts changed'):
                budget.run(folder, {})
            # Historical results can still be inspected offline.
            self.assertEqual(budget.report(folder, budget.load(folder))['paired_cases'], 0)

    def test_document_transcript_uses_frozen_packet_and_rejects_replacement(self):
        case = evaluation.load_cases('documents')[0]
        class Fixed:
            last_metadata = {}
            def check(self):
                return 'subscription'
            def answer(self, prompt, timeout):
                data = json.loads(prompt.split('INPUT_JSON:\n')[1])
                self_seen.append(data['question'])
                return answer(case['expected'])
        self_seen = []
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'batch'
            manifest = evaluate.create_batch(folder, [case], 1)
            evaluate.run_batch(folder, {'codex': Fixed(), 'claude': Fixed()})
            self.assertEqual(self_seen, [evaluation.question(case)] * 5)
            changed = copy.deepcopy(manifest)
            changed['cases'][0]['documents'][0]['text'] = 'Changed source'
            with self.assertRaisesRegex(ValueError, 'does not belong'):
                evaluate.records(folder, changed)
