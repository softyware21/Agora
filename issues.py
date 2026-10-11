"""Keep model-reported issue outcomes separate from citation checks."""
from attribution import turn_id
from source_evidence import block, bounded
from sources import normalize

STATUSES = ('agreed', 'disputed', 'insufficient_information')


def participant_positions(turns):
    """Read each participant's latest declaration, never the summarizer's copy."""
    latest = {}
    for index, turn in enumerate(turns):
        if turn.get('phase') in ('initial', 'review') and turn.get('provider') in ('codex', 'claude'):
            latest[turn['provider']] = (index, turn)
    rows = []
    for provider in ('codex', 'claude'):
        if provider not in latest:
            continue
        index, turn = latest[provider]
        row = {'provider': provider, 'turn_id': turn_id(index), 'status': 'unavailable'}
        rows.append(row)
        entries, status = block(turn['text'], 'agora-position')
        if status != 'parsed' or len(entries) != 1:
            continue
        entry = entries[0]
        if (not isinstance(entry, dict) or set(entry) != {'disposition', 'conclusion', 'conditions'}
                or entry['disposition'] not in ('ready', 'blocked', 'conditional', 'user_choice', 'undetermined')
                or not bounded(entry, 'conclusion', 600)
                or not isinstance(entry['conditions'], list) or not 1 <= len(entry['conditions']) <= 4
                or any(not isinstance(value, str) or not 1 <= len(value.strip()) <= 500 for value in entry['conditions'])):
            continue
        row.update(status='declared', **entry)
    status = 'unavailable'
    if len(rows) == 2 and all(row['status'] == 'declared' for row in rows):
        status = 'same_category' if rows[0]['disposition'] == rows[1]['disposition'] else 'different_categories'
    return {'status': status, 'positions': rows}


def ledger(turns):
    summaries = [t for t in turns if t['phase'] == 'summary']
    if not summaries:
        return {'status': 'pending', 'issues': []}
    entries, status = block(summaries[-1]['text'], 'agora-issues')
    latest = {}
    lookup = {}
    for i, turn in enumerate(turns):
        if turn['phase'] != 'summary':
            latest[turn['provider']] = turn_id(i)
            lookup[turn_id(i)] = turn
    result = []
    for index, entry in enumerate(entries, 1):
        row = {'id': f'I{index:02d}', 'status': 'unverified', 'model_status': None,
               'topic': '', 'reason': '', 'next_step': '', 'positions': [], 'citation_status': 'invalid'}
        result.append(row)
        if not (bounded(entry, 'topic', 300) and bounded(entry, 'reason', 600)
                and bounded(entry, 'next_step', 600) and entry.get('status') in STATUSES
                and isinstance(entry.get('positions'), list) and len(entry['positions']) == 2):
            continue
        row.update(topic=entry['topic'], model_status=entry['status'], reason=entry['reason'], next_step=entry['next_step'])
        seen = set()
        valid = True
        for position in entry['positions']:
            item = {'status': 'invalid'}
            row['positions'].append(item)
            if not (bounded(position, 'turn_id', 10) and bounded(position, 'position', 500)
                    and bounded(position, 'quote', 400, 8)):
                valid = False
                continue
            item.update(position)
            turn = lookup.get(position['turn_id'])
            if not turn or latest.get(turn['provider']) != position['turn_id'] or turn['provider'] in seen:
                item['status'] = 'not_latest_position'
                valid = False
                continue
            seen.add(turn['provider'])
            item['provider'] = turn['provider']
            item['actual_provider'] = turn.get('metadata', {}).get('actual_provider', turn['provider'])
            item['status'] = 'quote_found' if normalize(position['quote']) in normalize(turn['text']) else 'quote_not_found'
            valid &= item['status'] == 'quote_found'
        if valid and seen == set(latest):
            row.update(status=row['model_status'], citation_status='quotes_found')
    return {'status': status, 'issues': result}


def overview(board):
    if board['status'] != 'parsed' or not board['issues']:
        return 'Issue outcomes unavailable; no agreement can be inferred.'
    counts = {status: sum(i['status'] == status for i in board['issues']) for status in (*STATUSES, 'unverified')}
    return 'Model-reported issues: ' + ', '.join(f'{key}={value}' for key, value in counts.items()) + '. Not factual verification.'
