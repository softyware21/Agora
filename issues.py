"""Keep model-reported issue outcomes separate from citation checks."""
from attribution import turn_id
from source_evidence import block, bounded
from sources import normalize

STATUSES = ('agreed', 'disputed', 'insufficient_information')


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
