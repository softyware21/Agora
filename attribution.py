"""Check cited speech and full-answer visibility, not the meaning of agreement."""
from source_evidence import block, bounded
from sources import normalize

VERSION = 1


def turn_id(index):
    return f'T{index + 1:03d}'


def visible(turns, phase, round_number):
    if phase == 'initial':
        return []
    return [turn_id(i) for i, t in enumerate(turns)
            if t['phase'] != 'summary' and (phase == 'summary' or t['round'] == round_number - 1)]


def context(turns, phase, round_number):
    if phase == 'initial':
        return None
    full = visible(turns, phase, round_number)
    history = [dict(id=turn_id(i), provider=t['provider'], phase=t['phase'], round=t['round'],
                    full_answer_ids=visible(turns[:i], t['phase'], t['round']))
               for i, t in enumerate(turns) if t['phase'] != 'summary' and
               (phase == 'summary' or t['round'] < round_number)]
    return {'full_answer_ids': full, 'turns': history}


def check(summary, prior):
    entries, status = block(summary, 'agora-attributions')
    lookup = {turn_id(i): (i, t) for i, t in enumerate(prior)}
    checks = []
    for entry in entries:
        row = {'status': 'unverified', 'claim': '', 'turn_id': '', 'quote': '', 'responds_to': None}
        checks.append(row)
        if not (bounded(entry, 'claim', 500) and bounded(entry, 'turn_id', 10)
                and bounded(entry, 'quote', 400, 8)
                and (entry.get('responds_to') is None or bounded(entry, 'responds_to', 10))):
            row['reason'] = 'Invalid attribution declaration.'
            continue
        row.update({key: entry.get(key) for key in ('claim', 'turn_id', 'quote', 'responds_to')})
        source = lookup.get(row['turn_id'])
        if source is None:
            row['reason'] = 'Cited turn does not exist before the summary.'
            continue
        index, turn = source
        row['provider'] = turn['provider']
        row['actual_provider'] = turn.get('metadata', {}).get('actual_provider', turn['provider'])
        if normalize(row['quote']) not in normalize(turn['text']):
            row.update(status='quote_not_found', reason='Quote does not occur in the cited answer.')
        elif row['responds_to'] is not None and row['responds_to'] not in visible(prior[:index], turn['phase'], turn['round']):
            row.update(status='context_not_available', reason='The cited speaker did not receive that full answer. This does not verify a response or agreement.')
        else:
            row.update(status='quote_and_context_match' if row['responds_to'] else 'quote_found',
                       reason='Quote and any declared full-answer visibility match. The interpretation of this quote remains unverified.')
    return {'status': status, 'checks': checks}


def ledger(turns):
    return [dict(check(t['text'], turns[:i]), turn=turn_id(i))
            for i, t in enumerate(turns) if t['phase'] == 'summary']
