"""Local UI jobs backed by the existing debate runner."""
import copy
from datetime import datetime
import json
from pathlib import Path
import re
import tempfile
import threading
import time
import uuid

import agora
import automatic
import continue_debate
import models
import judgment
import run_state
import sources


class ControlledProvider:
    def __init__(self, provider, stopped, progress):
        self.provider, self.stopped, self.progress = provider, stopped, progress
        self.name, self.model = provider.name, getattr(provider, 'model', None)

    @property
    def last_metadata(self):
        return getattr(self.provider, 'last_metadata', {})

    def guard(self):
        if self.stopped.is_set():
            raise agora.AgoraError('Stopped after the last completed answer. Resume when ready.', 'user_stop')

    def check(self):
        self.guard()
        return self.provider.check()

    def metadata(self):
        return self.provider.metadata() if hasattr(self.provider, 'metadata') else {}

    def answer(self, prompt, timeout):
        self.guard()
        phase = json.loads(prompt.split('INPUT_JSON:\n', 1)[1])['phase']
        self.progress(f'{self.name}: {phase}')
        return self.provider.answer(prompt, timeout)


class App:
    def __init__(self, root=None, provider_factory=None):
        self.root = (Path(root) if root else agora.ROOT / 'runs').resolve()
        self.factory = provider_factory or agora.create_providers
        self.lock = threading.Lock()
        self.thread = None
        self.stopped = threading.Event()
        self.job = {'status': 'idle', 'run_id': None, 'phase': '', 'error': None}

    def folder(self, run_id):
        if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,100}', run_id):
            raise ValueError('Invalid discussion ID.')
        folder = (self.root / run_id).resolve()
        if folder.parent != self.root:
            raise ValueError('Discussion must be inside the local runs directory.')
        return folder

    def record(self, run_id):
        with run_state.io_lock:
            return self._record(run_id)

    def _record(self, run_id):
        folder = self.folder(run_id)
        for name in ('transcript.json', 'parent.json'):
            if (folder / name).resolve().parent != folder:
                raise ValueError('Discussion files must stay inside their directory.')
        data = json.loads((folder / 'transcript.json').read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('prompt_version'), str):
            raise ValueError('This discussion uses an unsupported transcript format.')
        return run_state.load(folder, data['prompt_version'])

    def state(self):
        with self.lock:
            return dict(self.job, stopping=self.stopped.is_set(), active=bool(self.thread and self.thread.is_alive()))

    def history(self):
        result = []
        superseded = set()
        if not self.root.exists():
            return result
        for folder in sorted(self.root.iterdir(), key=lambda p: p.name, reverse=True):
            if not folder.is_dir() or not (folder / 'transcript.json').is_file():
                continue
            try:
                record = self.record(folder.name)
                if automatic.load(folder) and record.get('continuation'):
                    superseded.add(Path(record['continuation']['parent_directory']).name)
                result.append({'id': folder.name, 'question': record['question'], 'status': record['status'],
                               'started_at': record.get('started_at'), 'turns': len(record['turns']),
                               'outcomes': [item['status'] for item in record.get('issue_outcomes', {}).get('issues', [])]})
            except (ValueError, OSError, run_state.StateError):
                result.append({'id': folder.name, 'question': 'Unreadable discussion', 'status': 'unavailable', 'turns': 0})
        return sorted([item for item in result if item['id'] not in superseded], key=lambda item: item.get('started_at') or '', reverse=True)

    def detail(self, run_id):
        record = self.record(run_id)
        mixed = all(t.get('metadata', {}).get('actual_provider', t['provider']) == t['provider'] for t in record['turns'])
        try:
            note, note_error = judgment.load(self.folder(run_id)), None
        except (ValueError, OSError):
            note, note_error = None, 'Decision notes could not be read. Keep the original file.'
        policy = automatic.load(self.folder(run_id))
        previous = record.get('continuation', {}).get('parent_directory') if policy else None
        return {'id': run_id, 'record': record, 'judgment': note, 'judgment_error': note_error, 'automatic': policy,
                'previous_run': Path(previous).name if previous else None,
                'can_resume': mixed and record['status'] != 'completed' and record['prompt_version'] == agora.prompt_version(),
                'can_continue': mixed and record['status'] == 'completed' and record['rounds'] < 12}

    def save_judgment(self, payload):
        run_id = payload.get('run_id')
        self.record(run_id)
        return judgment.save(self.folder(run_id), payload)

    def plan(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('Expected discussion settings.')
        mode = payload.get('mode', 'new')
        if mode not in ('new', 'resume', 'continue'):
            raise ValueError('Unknown action.')
        timeout, deadline = payload.get('timeout', 180), payload.get('deadline', 600)
        if type(timeout) is not int or not 10 <= timeout <= 600 or type(deadline) is not int or not 1 <= deadline <= 7200:
            raise ValueError('Timeout must be 10-600 seconds; total deadline must be 1-7,200 seconds.')
        parent_id = payload.get('parent')
        if mode == 'resume':
            detail = self.detail(parent_id)
            if not detail['can_resume']:
                raise ValueError('This discussion cannot be resumed here. Use its original runner or start a new discussion.')
            record = run_state.load(self.folder(parent_id), agora.prompt_version())
            selection = record.get('model_selection')
            pending = run_state.steps(record['rounds'], selection)[len(record['turns']):]
            settings = {'question': record['question'], 'rules': record['rules'], 'rounds': record['rounds'],
                        'model_selection': selection, 'source_urls': [], 'note': ''}
        else:
            parent = self.record(parent_id) if mode == 'continue' else None
            if parent and not self.detail(parent_id)['can_continue']:
                raise ValueError('Only a completed discussion below 12 rounds can continue here.')
            selection = models.validate(payload.get('model_selection', parent.get('model_selection') if parent else None))
            question = parent['question'] if parent else payload.get('question', '')
            rules = payload.get('rules', parent['rules'] if parent else agora.DEFAULT_RULES)
            rounds = payload.get('rounds', 1)
            urls, note = payload.get('source_urls', []), payload.get('note', '')
            if (not isinstance(question, str) or not question.strip() or len(question) > 12000
                    or not isinstance(rules, str) or len(rules) > 8000):
                raise ValueError('Enter a question up to 12,000 characters and rules up to 8,000 characters.')
            if type(rounds) is not int or not 1 <= rounds <= 3:
                raise ValueError('Choose 1-3 review rounds.')
            if not isinstance(urls, list) or len(urls) > 5 or any(not isinstance(url, str) or len(url) > 2048 for url in urls):
                raise ValueError('Provide up to five public HTTPS source URLs.')
            urls = list(dict.fromkeys(sources.validate_url(url) for url in urls))
            if not isinstance(note, str) or len(note) > 8000:
                raise ValueError('A supplement may contain up to 8,000 characters.')
            if parent:
                urls = continue_debate.validate(parent, rounds, note, rules, urls)
            pending = run_state.steps(rounds, selection)[2 if parent else 0:]
            settings = {'question': question, 'rules': rules, 'rounds': rounds, 'source_urls': urls,
                        'model_selection': selection, 'note': note}
        policy = automatic.load(self.folder(parent_id)) if mode == 'resume' else None
        automatic_mode = payload.get('automatic', False)
        if type(automatic_mode) is not bool:
            raise ValueError('Automatic review must be a boolean.')
        if mode != 'resume' and automatic_mode:
            target = (parent['rounds'] if parent else 0) + rounds
            policy = {'target_round': target, 'reason': 'running', 'previous': ''}
            settings['rounds'] = 1
            pending = run_state.steps(1, selection)[2 if parent else 0:]
        if policy:
            current_round = record['rounds'] if mode == 'resume' else (parent['rounds'] if parent else 0) + 1
            pending += [(name, phase, number) for number in range(current_round + 1, policy['target_round'] + 1)
                        for name, phase in [('codex', 'review'), ('claude', 'review'),
                                            (models.validate(selection)['summary_provider'], 'summary')]]
        return {'automatic': policy, 'mode': mode, 'parent': parent_id, 'timeout': timeout, 'deadline': deadline, **settings,
                'calls': len(pending), 'by_provider': {name: sum(n == name for n, _, _ in pending) for name in ('codex', 'claude')},
                'models': models.describe(selection), 'allowance': 'unavailable'}

    def start(self, payload):
        plan = self.plan(payload)
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError('A discussion is already running. Wait for it to finish or stop it first.')
            run_id = plan['parent'] if plan['mode'] == 'resume' else 'ui-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
            self.stopped = threading.Event()
            self.job = {'status': 'running', 'run_id': run_id, 'origin': run_id, 'phase': 'Preparing discussion', 'error': None}
            self.thread = threading.Thread(target=self.work, args=(copy.deepcopy(plan), run_id), name='agora-discussion')
            self.thread.start()
        return {'run_id': run_id}

    def progress(self, text):
        with self.lock:
            self.job['phase'] = text

    def work(self, plan, run_id):
        policy = plan['automatic']
        try:
            folder = self.folder(run_id)
            selection = plan['model_selection']
            resume = plan['mode'] != 'new'
            if plan['mode'] == 'continue':
                record = continue_debate.prepare(self.folder(plan['parent']), folder, plan['rounds'],
                    plan['note'], plan['rules'], plan['source_urls'], selection)
                rounds = record['rounds']
            else:
                rounds = plan['rounds']
            if policy:
                automatic.save(folder, dict(policy, reason='running'))
            deadline = time.monotonic() + plan['deadline']
            with tempfile.TemporaryDirectory(prefix='agora-ui-') as isolated:
                providers = {key: ControlledProvider(provider, self.stopped, self.progress)
                             for key, provider in self.factory(isolated, selection).items()}
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining < 1:
                        raise agora.AgoraError('The overall execution deadline was reached.', 'deadline')
                    record = agora.debate(providers, plan['question'], plan['rules'], rounds, plan['timeout'], folder,
                        deadline_seconds=remaining, resume=resume,
                        source_urls=plan['source_urls'] if not resume else None, model_selection=selection)
                    if not policy:
                        break
                    reason, signature = automatic.assess(record, policy)
                    if self.stopped.is_set():
                        reason = 'user_stop'
                    elif time.monotonic() >= deadline and reason == 'running':
                        reason = 'deadline'
                    policy = dict(policy, reason=reason, previous=signature)
                    automatic.save(folder, policy)
                    if reason != 'running':
                        break
                    next_id = 'ui-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
                    child = self.folder(next_id)
                    record = continue_debate.prepare(folder, child, 1,
                        'Reassess the remaining disputed issues. Address counterarguments and state what would change your conclusion. Do not force agreement.')
                    automatic.save(child, policy)
                    folder, rounds, resume = child, record['rounds'], True
                    with self.lock:
                        self.job['run_id'] = next_id
            with self.lock:
                self.job.update(status='completed', phase='Completed')
        except (agora.AgoraError, run_state.StateError, ValueError, OSError) as exc:
            if plan['automatic'] and getattr(exc, 'reason', None) in ('user_stop', 'deadline'):
                try:
                    automatic.save(folder, dict(policy, reason=exc.reason))
                except (ValueError, OSError):
                    pass
            with self.lock:
                self.job.update(status='stopped', phase='Stopped', error=str(exc))
        except Exception:
            with self.lock:
                self.job.update(status='stopped', phase='Stopped', error='Unexpected local error. Saved answers remain in the runs directory.')

    def stop(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                self.stopped.set()
        return self.state()
