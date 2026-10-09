"""Continue a completed discussion in a new directory without changing its history."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import uuid

import agora
import issues
import run_state
import sources
import models


def parent_record(folder):
    raw = (folder / 'transcript.json').read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get('prompt_version'), str):
        raise ValueError('Unsupported parent transcript.')
    record = run_state.load(folder, data['prompt_version'])
    if record['status'] != 'completed':
        raise ValueError('Parent is incomplete. Resume it before adding rounds.')
    if any(t.get('metadata', {}).get('actual_provider', t['provider']) != t['provider'] for t in record['turns']):
        raise ValueError('Single-model evaluation arms cannot be continued with mixed-model routing.')
    return record, raw


def validate(parent, add_rounds, note, rules, urls):
    if type(add_rounds) is not int or not 1 <= add_rounds <= 3 or parent['rounds'] + add_rounds > 12:
        raise ValueError('Add 1-3 review rounds, with at most 12 rounds in a discussion chain.')
    if not isinstance(note, str) or len(note) > 8000 or not isinstance(rules, str) or len(rules) > 8000:
        raise ValueError('Supplement and rules must each be at most 8,000 characters.')
    if sum(len(item['text']) for item in parent.get('continuation', {}).get('supplements', [])) + len(note) > 16000:
        raise ValueError('Combined supplements exceed 16,000 characters; start a new discussion.')
    old_urls = {s['url'] for s in parent.get('sources', [])}
    added = list(dict.fromkeys(url for url in urls if url not in old_urls))
    if len(parent.get('sources', [])) + len(added) > 5:
        raise ValueError('At most five total source snapshots are supported.')
    return added


def prepare(parent_folder, destination, add_rounds=1, note='', rules=None, urls=None, model_selection=None):
    parent_folder, destination = parent_folder.resolve(), destination.resolve()
    # Read and validate under the parent lock, then never write to its transcript.
    with run_state.locked(parent_folder):
        parent, raw = parent_record(parent_folder)
    current_rules = parent['rules'] if rules is None else rules
    selection = parent.get('model_selection') if model_selection is None else models.validate(model_selection)
    added = validate(parent, add_rounds, note, current_rules, urls or [])
    destination.mkdir(parents=True, exist_ok=False)
    with run_state.locked(destination):
        snapshots = copy.deepcopy(parent.get('sources', []))
        for source in sources.collect(added):
            source['id'] = f'S{len(snapshots) + 1:02d}'
            snapshots.append(source)
        (destination / 'parent.json').write_bytes(raw)
        link = {'parent_directory': str(parent_folder), 'parent_sha256': hashlib.sha256(raw).hexdigest(),
                'inherited_turns': len(parent['turns']) - 1, 'add_rounds': add_rounds, 'note': note,
                'supplements': copy.deepcopy(parent.get('continuation', {}).get('supplements', []))}
        if note:
            link['supplements'].append({'after_round': parent['rounds'], 'text': note})
        rounds = parent['rounds'] + add_rounds
        inherited = copy.deepcopy(parent['turns'][:-1])
        for turn in inherited:
            turn.setdefault('source_ids', [s['id'] for s in parent.get('sources', [])])
        record = {'schema_version': 1, 'prompt_version': agora.prompt_version(), 'status': 'stopped',
                  'question': parent['question'], 'rules': current_rules, 'rounds': rounds,
                  'sources': snapshots, 'turns': inherited,
                  'summary': None, 'attempts': [], 'continuation': link,
                  'started_at': datetime.now(timezone.utc).isoformat(),
                  'stop_reason': 'ready_to_continue', 'error': None,
                  'config_hash': run_state.fingerprint(parent['question'], current_rules, rounds,
                                                       agora.prompt_version(), snapshots, link, selection)}
        if selection is not None:
            record['model_selection'] = selection
        agora.save(destination, record)
        run_state.load(destination, agora.prompt_version())
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from', dest='parent', type=Path, required=True)
    parser.add_argument('--add-rounds', type=int, default=1)
    parser.add_argument('--note', default='', help='New information or a question to focus on')
    parser.add_argument('--rules', help='Replace rules for the added rounds only')
    parser.add_argument('--source', action='append', default=[], help='Append a public HTTPS source')
    parser.add_argument('--plan', action='store_true', help='Preview calls and changes without model calls or downloads')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--deadline', type=int, default=600)
    models.add_arguments(parser)
    args = parser.parse_args()
    try:
        if not 10 <= args.timeout <= 600 or args.deadline < 1:
            raise ValueError('Timeout must be 10-600 seconds and deadline must be positive.')
        parent, _ = parent_record(args.parent)
        selection = models.from_args(args, parent.get('model_selection'))
        rules = parent['rules'] if args.rules is None else args.rules
        added = validate(parent, args.add_rounds, args.note, rules, args.source)
        summary = selection['summary_provider']
        print(models.describe(selection))
        print(f'Additional model calls: {2 * args.add_rounds + 1} '
              f"(codex {args.add_rounds + (summary == 'codex')}, claude {args.add_rounds + (summary == 'claude')}).")
        print(f'New source URLs: {len(added)}; rules changed: {rules != parent["rules"]}; supplement: {bool(args.note)}')
        print(issues.overview(issues.ledger(parent['turns'])))
        if args.plan:
            return 0
        destination = agora.ROOT / 'runs' / ('continued-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
        print(f'Continuation directory: {destination}', flush=True)
        record = prepare(args.parent, destination, args.add_rounds, args.note, args.rules, args.source, selection)
        with tempfile.TemporaryDirectory(prefix='agora-continue-') as isolated:
            providers = agora.create_providers(isolated, selection)
            result = agora.debate(providers, record['question'], record['rules'], record['rounds'], args.timeout,
                                  destination, deadline_seconds=args.deadline, resume=True)
        print(issues.overview(result['issue_outcomes']))
        print(f"Completed: {destination / 'report.md'}")
        return 0
    except (agora.AgoraError, run_state.StateError, OSError, ValueError, KeyboardInterrupt) as exc:
        print(f'Stopped: {exc}', file=sys.stderr)
        print('If a continuation was saved, use agora.py --resume with its directory.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
