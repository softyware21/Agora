"""Compare mixed-model and single-model deliberation with equal call counts."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import uuid

import agora
import evaluate
import evaluation
import run_state

ARMS = ('mixed', 'codex-only', 'claude-only')
LABELS = {'codex': 'participant_A', 'claude': 'participant_B'}


def neutral_roles(value):
    if isinstance(value, list):
        return [neutral_roles(item) for item in value]
    if isinstance(value, dict):
        return {key: LABELS.get(item, item) if key == 'provider' and isinstance(item, str)
                else neutral_roles(item) for key, item in value.items()}
    return value


class RoutedProvider:
    def __init__(self, provider, name, role, arm):
        self.provider, self.name = provider, name
        self.role, self.arm = role, arm
        self.last_metadata = {}

    def check(self):
        return self.provider.check()

    def metadata(self):
        return dict(self.provider.metadata(), actual_provider=self.name)

    def answer(self, prompt, timeout):
        prefix, payload = prompt.split('INPUT_JSON:\n', 1)
        data = neutral_roles(json.loads(payload))
        data['execution_context'] = {
            'speaker': LABELS[self.role],
            'participants': {LABELS[r]: r if self.arm == 'mixed' else self.name for r in LABELS},
            'same_provider': self.arm != 'mixed'}
        prompt = (prefix + 'Use participant_A and participant_B for speaker attribution. '
                  'The execution_context identifies the actual providers. Role labels do not imply different models. '
                  'Do not describe same-provider agreement as cross-model corroboration.\nINPUT_JSON:\n'
                  + json.dumps(data, ensure_ascii=False))
        text = self.provider.answer(prompt, timeout)
        self.last_metadata = dict(self.provider.last_metadata, actual_provider=self.name,
                                  participant=LABELS[self.role], routing_version=2)
        return text


def create(folder, cases, rounds=1):
    evaluation.validate_cases(cases)
    folder.mkdir(parents=True, exist_ok=False)
    children = {}
    for arm in ARMS:
        children[arm] = evaluate.create_batch(folder / arm, cases, rounds)['fingerprint']
    config = {'version': 2, 'children': children}
    config['fingerprint'] = evaluate.digest(config)
    evaluate.write_json(folder / 'comparison.json', config)


def load(folder):
    config = json.loads((folder / 'comparison.json').read_text(encoding='utf-8'))
    if (not isinstance(config, dict) or config.get('version') not in (1, 2)
            or config.get('fingerprint') != evaluate.digest({k: v for k, v in config.items() if k != 'fingerprint'})
            or set(config.get('children', {})) != set(ARMS)):
        raise ValueError('Invalid comparison settings.')
    manifests = {arm: evaluate.load_batch(folder / arm) for arm in ARMS}
    for arm, manifest in manifests.items():
        if manifest['fingerprint'] != config['children'][arm]:
            raise ValueError('Comparison child settings changed.')
        if (manifest['cases'], manifest['rounds']) != (manifests['mixed']['cases'], manifests['mixed']['rounds']):
            raise ValueError('Comparison conditions differ.')
    return manifests


def arm_records(folder, manifests):
    saved = {arm: evaluate.records(folder / arm, manifests[arm]) for arm in ARMS}
    version = json.loads((folder / 'comparison.json').read_text(encoding='utf-8'))['version']
    for arm in ARMS:
        for record in saved[arm].values():
            if not record:
                continue
            for turn in record['turns']:
                expected = turn['provider'] if arm == 'mixed' else arm.removesuffix('-only')
                if turn.get('metadata', {}).get('actual_provider') != expected:
                    raise ValueError('Saved response routing does not match this comparison arm.')
                if version == 2 and turn.get('metadata', {}).get('routing_version') != 2:
                    raise ValueError('Saved routing prompt version changed.')
    return saved


def report(folder, manifests):
    saved = arm_records(folder, manifests)
    for arm in ARMS:
        evaluate.report(folder / arm, manifests[arm])
        path = folder / arm / 'comparison.md'
        notice = (f'> Comparison arm: {arm}. Provider names below are role labels. '
                  'In a single-model arm both roles, including the summary, use the named provider. '
                  'Resume through budget_compare.py at the parent directory.\n\n')
        text = path.read_text(encoding='utf-8')
        text = text.replace('Codex initial', 'Participant A initial').replace('Claude initial', 'Participant B initial')
        text = text.replace('is written by Codex', 'is written by participant A')
        path.write_text(notice + text, encoding='utf-8')
    rows = []
    for case in manifests['mixed']['cases']:
        scores = {}
        complete = True
        for arm in ARMS:
            record = saved[arm][case['id']]
            complete &= bool(record and record['status'] == 'completed')
            scores[arm] = evaluation.compare(record, case)['debate']
        rows.append({'id': case['id'], 'complete': complete, 'scores': scores})
    paired = [r for r in rows if r['complete']]
    totals = {arm: sum(r['scores'][arm]['status'] == 'pass' for r in paired) for arm in ARMS}
    result = {'paired_cases': len(paired), 'passes': totals, 'cases': rows}
    evaluate.write_json(folder / 'scores.json', result)
    count = 3 + 2 * manifests['mixed']['rounds']
    lines = ['# Equal-call comparison', '',
             f'Each arm uses {count} calls per case: two independent answers, reviews, then a summary.',
             'Single-model arms route every role to the same provider. They receive no mixed-arm answers.',
             'Call counts are equal; tokens, latency, compute, and provider-specific usage are not controlled.',
             'The fixed execution order is mixed, Codex-only, then Claude-only. Model drift and order effects remain possible.', '',
             f'Completed cases across all three arms: {len(paired)} / {len(rows)}', '',
             '| Case | Mixed | Codex only | Claude only |', '| --- | --- | --- | --- |']
    for row in rows:
        lines.append('| ' + row['id'] + ' | ' + ' | '.join(row['scores'][a]['status'] for a in ARMS) + ' |')
    lines += ['', 'Only cases completed in all arms enter totals. Format errors count as non-passes.', '',
              '| Arm | Passes |', '| --- | --- |']
    lines += [f'| {a} | {totals[a]} / {len(paired)} |' for a in ARMS]
    lines += ['', 'Answer-field scores do not grade explanation quality. Read each arm report for the full responses.',
              'Transcript provider fields retain the original role labels; actual_provider metadata records the routing.', '']
    lines += [f'- [{a} answers and scores]({a}/comparison.md)' for a in ARMS]
    (folder / 'comparison.md').write_text('\n'.join(lines), encoding='utf-8')
    return result


def run(folder, providers, timeout=180, deadline=600):
    with run_state.locked(folder):
        manifests = load(folder)
        # Validate all arms before making calls, including those not reached yet.
        saved = arm_records(folder, manifests)
        version = json.loads((folder / 'comparison.json').read_text(encoding='utf-8'))['version']
        if version == 1 and any(not r or r['status'] != 'completed' for arm in saved.values() for r in arm.values()):
            raise ValueError('Routing prompts changed. Keep the old reports and start a new comparison.')
        remaining = sum(3 + 2 * manifests[a]['rounds'] - (len(r['turns']) if r else 0)
                        for a in ARMS for r in saved[a].values())
        print(f'Total remaining calls across all arms: {remaining}', flush=True)
        try:
            for arm in ARMS:
                print(f'Comparison arm: {arm}', flush=True)
                routed = {}
                for role in ('codex', 'claude'):
                    actual = role if arm == 'mixed' else arm.removesuffix('-only')
                    if actual in providers:
                        routed[role] = RoutedProvider(providers[actual], actual, role, arm)
                evaluate.run_batch(folder / arm, routed, timeout, deadline)
        finally:
            report(folder, manifests)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--case', action='append')
    action.add_argument('--all', action='store_true')
    action.add_argument('--resume', type=Path)
    action.add_argument('--report', type=Path)
    parser.add_argument('--suite', choices=('basic', 'challenge'), default='challenge')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--deadline', type=int, default=600)
    args = parser.parse_args()
    try:
        if args.report:
            with run_state.locked(args.report):
                report(args.report, load(args.report))
            return 0
        if args.resume:
            folder = args.resume.resolve()
        else:
            cases = evaluation.load_cases(args.suite)
            if not args.case and not args.all:
                for case in cases:
                    print(case['id'])
                print('Select --case ID or --all. Each case uses 15 calls across three arms.')
                return 0
            selected = set(args.case or [c['id'] for c in cases])
            if selected - {c['id'] for c in cases}:
                raise ValueError('Unknown case ID.')
            folder = agora.ROOT / 'runs' / ('budget-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
            create(folder, [c for c in cases if c['id'] in selected])
        print(f'Comparison directory: {folder}', flush=True)
        manifests = load(folder)
        complete = all(r and r['status'] == 'completed'
                       for a in ARMS for r in evaluate.records(folder / a, manifests[a]).values())
        if complete:
            run(folder, {})
        else:
            with tempfile.TemporaryDirectory(prefix='agora-budget-') as isolated:
                providers = {n: agora.Provider(n, isolated) for n in ('codex', 'claude')}
                run(folder, providers, args.timeout, args.deadline)
        print(f"Comparison: {folder / 'comparison.md'}")
        return 0
    except (agora.AgoraError, run_state.StateError, OSError, ValueError, KeyboardInterrupt) as exc:
        print(f'Stopped: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
