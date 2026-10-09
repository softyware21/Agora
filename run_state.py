"""Transcript validation and one-writer locking."""
from contextlib import contextmanager
import hashlib
import json
import os
import copy
import models
import threading


# Windows readers can block atomic file replacement within the same process.
io_lock = threading.RLock()


class StateError(Exception):
    pass


def steps(rounds, model_selection=None):
    return ([('codex', 'initial', 0), ('claude', 'initial', 0)]
            + [(name, 'review', number) for number in range(1, rounds + 1)
               for name in ('codex', 'claude')]
            + [(models.validate(model_selection)['summary_provider'], 'summary', rounds)])


def fingerprint(question, rules, rounds, prompt_version, source_snapshots=None, continuation=None, model_selection=None):
    values = [question, rules, rounds, prompt_version, source_snapshots or []]
    if continuation is not None:
        values.append(continuation)
    if model_selection is not None:
        values.append({'model_selection': models.validate(model_selection)})
    data = json.dumps(values, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def validate_continuation(folder, record):
    link = record.get('continuation')
    if link is None:
        if record['rounds'] > 3:
            raise ValueError('More than three rounds require a continuation.')
        return
    if (not isinstance(link, dict) or type(link.get('add_rounds')) is not int or not 1 <= link['add_rounds'] <= 3
            or not isinstance(link.get('note'), str) or len(link['note']) > 8000
            or not isinstance(link.get('parent_directory'), str)):
        raise ValueError('Invalid continuation settings.')
    raw = (folder / 'parent.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != link.get('parent_sha256'):
        raise ValueError('Parent snapshot changed.')
    parent = json.loads(raw)
    if (not isinstance(parent, dict) or parent.get('status') != 'completed'
            or type(parent.get('rounds')) is not int or not 1 <= parent['rounds'] < 12
            or record['rounds'] != parent['rounds'] + link['add_rounds']
            or record['question'] != parent.get('question')):
        raise ValueError('Invalid parent discussion.')
    parent_turns = parent.get('turns')
    if (not isinstance(parent_turns, list) or len(parent_turns) != len(steps(parent['rounds']))
            or not all(isinstance(t, dict) for t in parent_turns)
            or parent_turns[-1].get('phase') != 'summary' or parent.get('summary') != parent_turns[-1].get('text')):
        raise ValueError('Incomplete parent discussion.')
    inherited = copy.deepcopy(parent_turns[:-1])
    for turn in inherited:
        turn.setdefault('source_ids', [s['id'] for s in parent.get('sources', [])])
    if link.get('inherited_turns') != len(inherited) or record['turns'][:len(inherited)] != inherited:
        raise ValueError('Inherited answers changed.')
    old_sources = parent.get('sources', [])
    if record.get('sources', [])[:len(old_sources)] != old_sources:
        raise ValueError('Inherited source snapshots changed.')
    supplements = copy.deepcopy(parent.get('continuation', {}).get('supplements', []))
    if link['note']:
        supplements.append({'after_round': parent['rounds'], 'text': link['note']})
    if link.get('supplements') != supplements or sum(len(item['text']) for item in supplements) > 16000:
        raise ValueError('Supplement history changed.')


def load(folder, prompt_version):
    with io_lock:
        return _load(folder, prompt_version)


def _load(folder, prompt_version):
    try:
        record = json.loads((folder / 'transcript.json').read_text(encoding='utf-8'))
        if not isinstance(record, dict) or record.get('schema_version') != 1:
            raise ValueError('Unsupported transcript version; keep the original and start a new run.')
        question, rules, rounds = record['question'], record['rules'], record['rounds']
        if (not isinstance(question, str) or not question.strip() or len(question) > 12000
                or not isinstance(rules, str) or len(rules) > 8000
                or type(rounds) is not int or not 1 <= rounds <= 12):
            raise ValueError('Invalid saved question, rules, or round count.')
        if record.get('prompt_version') != prompt_version:
            raise ValueError('Prompt version changed; start a new run.')
        snapshots = record.get('sources', [])
        if not isinstance(snapshots, list) or len(snapshots) > 5:
            raise ValueError('Invalid source snapshots.')
        for index, source in enumerate(snapshots, 1):
            if (not isinstance(source, dict) or source.get('id') != f'S{index:02d}'
                    or source.get('status') not in ('retrieved', 'unavailable')
                    or not isinstance(source.get('text'), str) or len(source['text']) > 12000):
                raise ValueError('Invalid source snapshot.')
            if source['status'] == 'retrieved':
                if (not all(isinstance(source.get(key), str) for key in ('url', 'final_url', 'retrieved_at', 'sha256'))
                        or source['sha256'] != hashlib.sha256(source['text'].encode()).hexdigest()):
                    raise ValueError('Source snapshot changed.')
        selection = record.get('model_selection')
        models.validate(selection)
        if record.get('config_hash') != fingerprint(question, rules, rounds, prompt_version, snapshots, record.get('continuation'), selection):
            raise ValueError('Saved settings changed; start a new run.')
        if record.get('status') not in ('running', 'stopped', 'completed'):
            raise ValueError('Invalid run status.')
        turns = record['turns']
        plan = steps(rounds, selection)
        if not isinstance(turns, list) or len(turns) > len(plan):
            raise ValueError('Invalid turn list.')
        for turn, expected in zip(turns, plan):
            if (not isinstance(turn, dict)
                    or (turn.get('provider'), turn.get('phase'), turn.get('round')) != expected
                    or not isinstance(turn.get('text'), str)
                    or not turn['text'].strip() or len(turn['text']) > 20000):
                raise ValueError('Turns are missing, reordered, or invalid.')
            if 'source_ids' in turn and (not isinstance(turn['source_ids'], list)
                    or any(not isinstance(sid, str) or sid not in {s['id'] for s in snapshots} for sid in turn['source_ids'])):
                raise ValueError('Invalid per-turn source availability.')
        validate_continuation(folder, record)
        if len(turns) == len(plan):
            if record.get('summary') != turns[-1]['text']:
                raise ValueError('Summary does not match the saved turn.')
        elif record.get('summary') is not None or record['status'] == 'completed':
            raise ValueError('Run is marked complete before all turns were saved.')
        attempts = record.get('attempts')
        if not isinstance(attempts, list) or not all(isinstance(a, dict) for a in attempts):
            raise ValueError('Invalid attempt history.')
        return record
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise StateError(f'Cannot resume this transcript: {exc}') from None


@contextmanager
def locked(folder):
    folder.mkdir(parents=True, exist_ok=True)
    # OS locks are released on exit, including a crash; the marker can stay on disk.
    with (folder / '.run.lock').open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise StateError('This run is already in use by another process.') from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
