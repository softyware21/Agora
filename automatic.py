"""Bound automatic reviews without treating consensus as proof."""
import json
import os
import tempfile

import run_state


REASONS = ('running', 'agreement', 'needs_information', 'assessment_unavailable',
           'repeated_positions', 'round_limit', 'deadline', 'user_stop')


def load(folder):
    path = folder / 'automatic.json'
    if path.resolve().parent != folder.resolve():
        raise ValueError('Automatic review settings must stay inside the discussion directory.')
    if not path.exists():
        return None
    with run_state.io_lock:
        data = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or type(data.get('target_round')) is not int
            or not 1 <= data['target_round'] <= 12 or data.get('reason') not in REASONS
            or not isinstance(data.get('previous', ''), str)):
        raise ValueError('Invalid automatic review settings.')
    return data


def save(folder, policy):
    folder.mkdir(parents=True, exist_ok=True)
    load(folder)
    with run_state.io_lock:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=folder, delete=False) as stream:
            json.dump(policy, stream, ensure_ascii=False)
            temporary = stream.name
        try:
            os.replace(temporary, folder / 'automatic.json')
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def assess(record, policy):
    board = record.get('issue_outcomes', {})
    issues = board.get('issues', [])
    if board.get('status') != 'parsed' or not issues or any(i['status'] == 'unverified' for i in issues):
        return 'assessment_unavailable', ''
    if any(i['status'] == 'insufficient_information' for i in issues):
        return 'needs_information', ''
    if all(i['status'] == 'agreed' for i in issues):
        return 'agreement', ''
    positions = sorted((i['topic'].strip().casefold(), i['status'],
                        sorted(p.get('position', '').strip().casefold() for p in i['positions'])) for i in issues)
    signature = json.dumps(positions, ensure_ascii=False)
    if policy.get('previous') == signature:
        return 'repeated_positions', signature
    if record['rounds'] >= policy['target_round']:
        return 'round_limit', signature
    return 'running', signature
