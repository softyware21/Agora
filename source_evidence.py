"""Keep quote matching separate from model judgments about support."""
import json
import re

from evidence import unique_fields
from sources import normalize


def block(text, name):
    pattern = rf'^```{name}[ \t]*\r?\n(.*?)^```[ \t]*\r?$'
    matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
    if not matches and f'```{name}' not in text:
        return [], 'not_declared'
    if len(matches) != 1 or text.count(f'```{name}') != 1:
        return [], 'invalid'
    try:
        entries = json.loads(matches[0], object_pairs_hook=unique_fields)
    except (ValueError, RecursionError):
        return [], 'invalid'
    if not isinstance(entries, list) or len(entries) > 5:
        return [], 'invalid'
    return entries, 'parsed'


def bounded(item, key, limit, minimum=1):
    value = item.get(key) if isinstance(item, dict) else None
    return isinstance(value, str) and minimum <= len(value.strip()) <= limit


def claims(text, turn_number, snapshots):
    entries, status = block(text, 'agora-sources')
    results = []
    lookup = {s['id']: s for s in snapshots}
    for index, entry in enumerate(entries, 1):
        check = {'id': f'T{turn_number:03d}-S{index:02d}', 'status': 'unverified',
                 'claim': '', 'source_id': '', 'quote': '', 'claimed_relation': 'unclear'}
        results.append(check)
        if not (bounded(entry, 'claim', 500) and bounded(entry, 'source_id', 10)
                and bounded(entry, 'quote', 400, 8)
                and entry.get('relation') in ('supports', 'contradicts', 'unclear')):
            check['reason'] = 'Invalid source declaration.'
            continue
        check.update(claim=entry['claim'].strip(), source_id=entry['source_id'].strip(),
                     quote=entry['quote'].strip(), claimed_relation=entry['relation'])
        source = lookup.get(check['source_id'])
        if not source or source.get('status') != 'retrieved':
            check['reason'] = 'Source was not retrieved.'
            continue
        check.update(url=source['final_url'], retrieved_at=source['retrieved_at'], sha256=source['sha256'])
        position = source['text'].find(normalize(check['quote']))
        check['status'] = 'quote_found' if position >= 0 else 'quote_not_found'
        check['reason'] = ('Quote found in the captured text; claim support still needs review.'
                           if position >= 0 else 'Quote not found in the captured text; this does not disprove the claim.')
        if position >= 0:
            check['context'] = source['text'][max(0, position - 200):position + len(normalize(check['quote'])) + 200]
    return {'status': status, 'checks': results}


def ledger(turns, snapshots):
    result = []
    for number, turn in enumerate(turns, 1):
        row = claims(turn['text'], number, snapshots)
        row.update(turn=number, provider=turn['provider'], phase=turn['phase'], round=turn['round'])
        raw_reviews, review_status = block(turn['text'], 'agora-source-reviews')
        prior = [r for r in result if turn['phase'] == 'summary' or r['round'] < turn['round']]
        targets = {c['id']: c for r in prior for c in r['checks']}
        assessments = []
        seen = set()
        for review in raw_reviews:
            item = {'status': 'unverified', 'target': '', 'relation': 'unclear', 'reason': ''}
            assessments.append(item)
            if not (bounded(review, 'target', 20) and bounded(review, 'reason', 500)
                    and review.get('relation') in ('supports', 'contradicts', 'unclear')):
                item['reason'] = 'Invalid source review.'
                continue
            target = review['target']
            item.update(target=target, reason=review['reason'], relation=review['relation'])
            if target in seen:
                item.update(reason='Duplicate review target.', relation='unclear')
                continue
            seen.add(target)
            if target in targets and targets[target]['status'] == 'quote_found':
                item['status'] = 'model_assessment'
            else:
                item.update(reason='Review target has no matched quote in an earlier round.', relation='unclear')
        row.update(review_status=review_status, assessments=assessments)
        result.append(row)
    return result
