"""Transcript validation and one-writer locking."""
from contextlib import contextmanager
import hashlib
import json
import os


class StateError(Exception):
    pass


def steps(rounds):
    return ([('codex', 'initial', 0), ('claude', 'initial', 0)]
            + [(name, 'review', number) for number in range(1, rounds + 1)
               for name in ('codex', 'claude')]
            + [('codex', 'summary', rounds)])


def fingerprint(question, rules, rounds, prompt_version, source_snapshots=None):
    data = json.dumps([question, rules, rounds, prompt_version, source_snapshots or []], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def load(folder, prompt_version):
    try:
        record = json.loads((folder / 'transcript.json').read_text(encoding='utf-8'))
        if not isinstance(record, dict) or record.get('schema_version') != 1:
            raise ValueError('Unsupported transcript version; keep the original and start a new run.')
        question, rules, rounds = record['question'], record['rules'], record['rounds']
        if (not isinstance(question, str) or not question.strip() or len(question) > 12000
                or not isinstance(rules, str) or len(rules) > 8000
                or type(rounds) is not int or not 1 <= rounds <= 3):
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
        if record.get('config_hash') != fingerprint(question, rules, rounds, prompt_version, snapshots):
            raise ValueError('Saved settings changed; start a new run.')
        if record.get('status') not in ('running', 'stopped', 'completed'):
            raise ValueError('Invalid run status.')
        turns = record['turns']
        plan = steps(rounds)
        if not isinstance(turns, list) or len(turns) > len(plan):
            raise ValueError('Invalid turn list.')
        for turn, expected in zip(turns, plan):
            if (not isinstance(turn, dict)
                    or (turn.get('provider'), turn.get('phase'), turn.get('round')) != expected
                    or not isinstance(turn.get('text'), str)
                    or not turn['text'].strip() or len(turn['text']) > 20000):
                raise ValueError('Turns are missing, reordered, or invalid.')
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
