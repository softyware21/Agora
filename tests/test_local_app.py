import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import agora
from local_app import App
import models
import run_state
from test_resume import Participant


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'runs'
        self.providers = []
        self.app = App(self.root, self.factory)

    def tearDown(self):
        if self.app.thread:
            self.app.stop()
            self.app.thread.join(5)
        self.temp.cleanup()

    def factory(self, cwd, selection):
        selection = models.validate(selection)
        providers = {n: Participant(n) for n in ('codex', 'claude')}
        for name, provider in providers.items():
            provider.model = selection[name]
        summary = selection['summary_provider']
        providers['summary'] = Participant(summary)
        providers['summary'].model = models.target(selection, summary, 'summary')
        self.providers.append(providers)
        return providers

    def finish(self, payload):
        result = self.app.start(payload)
        self.app.thread.join(5)
        self.assertFalse(self.app.thread.is_alive())
        self.assertEqual(self.app.state()['status'], 'completed', self.app.state())
        return result['run_id']

    def test_preview_validates_and_counts_without_creating_files_or_providers(self):
        selection = dict(models.validate(None), summary_provider='claude')
        with patch('sources.collect') as collect:
            plan = self.app.plan({'question': 'q', 'rounds': 2, 'model_selection': selection})
        self.assertEqual(plan['by_provider'], {'codex': 3, 'claude': 4})
        self.assertFalse(self.root.exists())
        self.assertFalse(self.providers)
        collect.assert_not_called()

    def test_start_saves_report_and_lists_history(self):
        run_id = self.finish({'question': '<script>not executable</script>'})
        detail = self.app.detail(run_id)
        self.assertEqual(len(detail['record']['turns']), 5)
        self.assertTrue(detail['can_continue'])
        self.assertFalse(detail['can_resume'])
        self.assertEqual(self.app.history()[0]['id'], run_id)
        self.assertEqual(self.app.history()[0]['outcomes'], [item['status'] for item in detail['record']['issue_outcomes']['issues']])
        self.assertTrue((self.root / run_id / 'report.md').is_file())

    def test_judgment_is_private_and_revision_checked(self):
        run_id = self.finish({'question': 'Decision fixture'})
        transcript = (self.root / run_id / 'transcript.json').read_bytes()
        data = {'run_id': run_id, 'revision': 0, 'decision': 'Try a pilot',
                'reason': 'Private reasoning', 'open_questions': 'Unknown timing'}
        with run_state.locked(self.root / run_id):
            saved = self.app.save_judgment(data)
        self.assertEqual(saved['revision'], 1)
        self.assertEqual(self.app.detail(run_id)['judgment']['decision'], 'Try a pilot')
        with self.assertRaisesRegex(ValueError, 'another window'):
            self.app.save_judgment(data)
        self.assertEqual((self.root / run_id / 'transcript.json').read_bytes(), transcript)
        child = self.finish({'mode': 'continue', 'parent': run_id})
        self.assertEqual(self.app.detail(child)['judgment']['revision'], 0)
        for providers in self.providers:
            for provider in providers.values():
                self.assertNotIn('Private reasoning', json.dumps(provider.calls))

    def test_invalid_judgment_never_replaces_saved_notes(self):
        run_id = self.finish({'question': 'q'})
        data = {'run_id': run_id, 'revision': 0, 'decision': 'x' * 4001, 'reason': '', 'open_questions': ''}
        with self.assertRaises(ValueError):
            self.app.save_judgment(data)
        self.assertFalse((self.root / run_id / 'judgment.json').exists())
        data.update(run_id='../escape', decision='x')
        with self.assertRaises(ValueError):
            self.app.save_judgment(data)
        (self.root / run_id / 'judgment.json').write_text('broken', encoding='utf-8')
        detail = self.app.detail(run_id)
        self.assertIsNone(detail['judgment'])
        self.assertEqual(detail['record']['status'], 'completed')
        with self.assertRaises(ValueError):
            self.app.save_judgment(dict(data, run_id=run_id))

    def test_stop_saves_current_answer_and_resume_only_calls_missing_turns(self):
        entered, release = threading.Event(), threading.Event()
        factory = self.factory

        def blocking(cwd, selection):
            providers = factory(cwd, selection)
            original = providers['codex'].answer

            def answer(prompt, timeout):
                entered.set()
                if not release.wait(4):
                    raise agora.AgoraError('Test release timed out.')
                return original(prompt, timeout)
            providers['codex'].answer = answer
            return providers

        self.app.factory = blocking
        run_id = self.app.start({'question': 'q'})['run_id']
        self.assertTrue(entered.wait(3))
        with self.assertRaisesRegex(ValueError, 'already running'):
            self.app.start({'question': 'another'})
        self.app.stop()
        release.set()
        self.app.thread.join(5)
        stopped = self.app.detail(run_id)
        self.assertEqual(stopped['record']['stop_reason'], 'user_stop')
        self.assertEqual(len(stopped['record']['turns']), 1)
        self.assertTrue(stopped['can_resume'])
        self.app.factory = factory
        self.assertEqual(self.app.plan({'mode': 'resume', 'parent': run_id})['calls'], 4)
        self.finish({'mode': 'resume', 'parent': run_id})
        self.assertEqual(sum(len(p.calls) for p in self.providers[-1].values()), 4)

    def test_continue_changes_models_in_three_calls_and_keeps_parent(self):
        parent = self.finish({'question': 'Original question'})
        before = (self.root / parent / 'transcript.json').read_bytes()
        settings = dict(models.validate(None), summary_provider='claude', summary_model='sonnet')
        payload = {'mode': 'continue', 'parent': parent, 'note': 'New information', 'model_selection': settings}
        self.assertEqual(self.app.plan(payload)['by_provider'], {'codex': 1, 'claude': 2})
        child = self.finish(payload)
        self.assertNotEqual(child, parent)
        self.assertEqual(self.app.history()[0]['id'], child)
        self.assertEqual(sum(len(p.calls) for p in self.providers[-1].values()), 3)
        self.assertEqual((self.root / parent / 'transcript.json').read_bytes(), before)
        self.assertEqual(self.app.detail(child)['record']['turns'][-1]['metadata']['requested_model'], 'sonnet')

    def test_invalid_settings_and_paths_are_rejected(self):
        for payload in ([], {'question': ''}, {'question': 'q', 'rounds': True},
                        {'question': 'q', 'source_urls': ['http://localhost/private']},
                        {'question': 'q', 'timeout': '180'}, {'question': 'q', 'deadline': 999999},
                        {'question': 'q', 'model_selection': {'codex': 'x'}}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.app.plan(payload)
        for run_id in ('../outside', 'nested/run', 'C:\\private', '', None):
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                self.app.folder(run_id)
        self.assertFalse(self.providers)

    def test_failed_provider_setup_is_visible_without_a_transcript(self):
        def fail(*args):
            raise agora.AgoraError('Install the official CLI first.')
        self.app.factory = fail
        self.app.start({'question': 'q'})
        self.app.thread.join(5)
        self.assertFalse(self.app.state()['active'])
        self.assertEqual(self.app.state()['status'], 'stopped')
        self.assertIn('Install', self.app.state()['error'])

    def test_saved_unfinished_run_can_resume_after_server_restart(self):
        run_id = self.finish({'question': 'q'})
        path = self.root / run_id / 'transcript.json'
        record = json.loads(path.read_text(encoding='utf-8'))
        record['turns'].pop()
        record.update(status='running', summary=None)
        path.write_text(json.dumps(record), encoding='utf-8')
        self.app = App(self.root, self.factory)
        self.assertEqual(self.app.plan({'mode': 'resume', 'parent': run_id})['calls'], 1)
        self.finish({'mode': 'resume', 'parent': run_id})

    def test_report_save_waits_for_an_active_reader(self):
        run_id = self.finish({'question': 'q'})
        record = self.app.record(run_id)
        entered, finished = threading.Event(), threading.Event()

        def save():
            entered.set()
            agora.save(self.root / run_id, record)
            finished.set()

        with run_state.io_lock:
            writer = threading.Thread(target=save)
            writer.start()
            self.assertTrue(entered.wait(1))
            self.assertFalse(finished.wait(.05))
            self.assertEqual(self.app.record(run_id)['summary'], record['summary'])
        writer.join(3)
        self.assertTrue(finished.is_set())


if __name__ == '__main__':
    unittest.main()
