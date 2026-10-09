"""Compare independent first answers with the final debate on fixed cases."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import uuid

import agora
import evaluation
from evidence import unique_fields
import run_state


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def create_batch(folder, cases, rounds):
    evaluation.validate_cases(cases)
    if type(rounds) is not int or not 1 <= rounds <= 3:
        raise ValueError('Rounds must be 1-3.')
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {'schema_version': 1, 'grading_version': evaluation.VERSION,
                'prompt_version': agora.prompt_version(), 'cases': cases, 'rounds': rounds,
                'created_at': datetime.now(timezone.utc).isoformat()}
    manifest['fingerprint'] = digest(manifest)
    write_json(folder / 'evaluation.json', manifest)
    return manifest


def load_batch(folder):
    manifest = json.loads((folder / 'evaluation.json').read_text(encoding='utf-8'), object_pairs_hook=unique_fields)
    if (not isinstance(manifest, dict) or manifest.get('schema_version') != 1
            or manifest.get('grading_version') != evaluation.VERSION
            or manifest.get('prompt_version') != agora.prompt_version()):
        raise ValueError('Evaluation or prompt version changed; start a new batch.')
    if manifest.get('fingerprint') != digest({k: v for k, v in manifest.items() if k != 'fingerprint'}):
        raise ValueError('Saved evaluation settings changed.')
    evaluation.validate_cases(manifest.get('cases'))
    if type(manifest.get('rounds')) is not int or not 1 <= manifest['rounds'] <= 3:
        raise ValueError('Invalid saved round count.')
    return manifest


def records(folder, manifest):
    result = {}
    for case in manifest['cases']:
        path = folder / case['id']
        record = run_state.load(path, manifest['prompt_version']) if (path / 'transcript.json').exists() else None
        if record and (record['question'] != evaluation.question(case) or record['rules'] != evaluation.rules(case)
                       or record['rounds'] != manifest['rounds'] or record.get('sources', [])):
            raise ValueError('Transcript does not belong to this evaluation case.')
        result[case['id']] = record
    return result


def report(folder, manifest):
    saved = records(folder, manifest)
    rows = []
    for case in manifest['cases']:
        record = saved[case['id']]
        rows.append({'id': case['id'], 'category': case['category'],
                     'status': record['status'] if record else 'not_started',
                     'saved_calls': len(record['turns']) if record else 0,
                     'scores': evaluation.compare(record, case)})
    paired = [row for row in rows if row['status'] == 'completed']
    names = ('codex', 'claude', 'debate')
    totals = {name: sum(row['scores'][name]['status'] == 'pass' for row in paired) for name in names}
    transitions = {}
    for name in names[:2]:
        transitions[name] = {
            'improved': sum(row['scores'][name]['status'] != 'pass' and row['scores']['debate']['status'] == 'pass' for row in paired),
            'regressed': sum(row['scores'][name]['status'] == 'pass' and row['scores']['debate']['status'] != 'pass' for row in paired)}
    result = {'grading_version': evaluation.VERSION, 'batch_fingerprint': manifest['fingerprint'],
              'paired_cases': len(paired), 'passes': totals, 'transitions': transitions, 'cases': rows}
    write_json(folder / 'scores.json', result)
    lines = ['# Evaluation comparison', '',
             'These checks grade declared answer fields, not explanations or general factual accuracy.',
             'The independent initial answers are reused as single-call baselines. The debate summary',
             'uses more calls and context and is written by Codex. This is not an equal-budget comparison.', '',
             f"Completed paired cases: {len(paired)} / {len(rows)}", '',
             '| Case | Run | Codex initial | Claude initial | Debate summary |',
             '| --- | --- | --- | --- | --- |']
    for row in rows:
        cells = [row['scores'][name]['status'] for name in names]
        lines.append(f"| {row['id']} | {row['status']} | " + ' | '.join(cells) + ' |')
    lines += ['', 'Only completed cases enter the paired totals. Format errors count as non-passes;',
              'missing turns remain pending. Failed and unfinished cases stay visible above.', '',
              '| Method | Cases passed |', '| --- | --- |']
    for name in names:
        lines.append(f'| {name} | {totals[name]} / {len(paired)} |')
    lines += ['', '| Baseline | Non-pass to pass | Pass to non-pass |', '| --- | --- | --- |']
    for name, counts in transitions.items():
        lines.append(f"| {name} | {counts['improved']} | {counts['regressed']} |")
    lines += ['', f"Saved model responses: {sum(row['saved_calls'] for row in rows)}.",
              'Failed attempts can also consume allowance. Provider versions and reported models',
              'are retained in each case transcript. No token cost or remaining allowance is estimated.', '',
              '## Review the explanations', '',
              'Check whether the prose agrees with the declared answer, whether the reasoning is valid,',
              'and whether uncertainty is handled honestly. A correct field can accompany a bad explanation.',
              'One small run does not establish that debate improves accuracy.', '']
    for case, row in zip(manifest['cases'], rows):
        lines += [f"### {case['id']}", '', evaluation.question(case), '',
                  'Answer key: `' + json.dumps(case['expected'], sort_keys=True) + '`', '',
                  case['rationale'], '']
        if saved[case['id']]:
            lines += [f"[Full answers and metadata]({case['id']}/report.md)", '']
        for name in names:
            score = row['scores'][name]
            lines += [f"- {name}: {score['status']}"]
            if score.get('reason'):
                lines.append('  ' + score['reason'])
            for key, field in score['fields'].items():
                lines.append(f"  {key}: {field['actual']} (expected {field['expected']}; correct: {field['correct']})")
        lines.append('')
    (folder / 'comparison.md').write_text('\n'.join(lines), encoding='utf-8')
    return result


def run_batch(folder, providers, timeout=180, deadline=600):
    if not 10 <= timeout <= 600 or deadline < 1:
        raise ValueError('Timeout must be 10-600 seconds and per-case deadline must be positive.')
    with run_state.locked(folder):
        manifest = load_batch(folder)
        saved = records(folder, manifest)
        remaining = sum(3 + 2 * manifest['rounds'] - (len(r['turns']) if r else 0) for r in saved.values())
        print(f'This uses your subscription allowance. Remaining model calls: {remaining}', flush=True)
        try:
            for case in manifest['cases']:
                if saved[case['id']] and saved[case['id']]['status'] == 'completed':
                    continue
                print(f"Evaluation case: {case['id']}", flush=True)
                agora.debate(providers, evaluation.question(case), evaluation.rules(case), manifest['rounds'],
                             timeout, folder / case['id'], deadline_seconds=deadline,
                             resume=saved[case['id']] is not None)
        finally:
            report(folder, manifest)


def main():
    parser = argparse.ArgumentParser(description='Compare independent answers with a debate on fixed cases')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--case', action='append', help='Run a case ID; repeat to select more')
    action.add_argument('--all', action='store_true', help='Run all cases (30 calls at one round)')
    action.add_argument('--resume', type=Path, help='Continue a saved evaluation directory')
    action.add_argument('--report', type=Path, help='Rebuild comparison files without model calls')
    parser.add_argument('--rounds', type=int, choices=(1, 2, 3))
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--deadline', type=int, default=600, help='Generation deadline per case attempt')
    args = parser.parse_args()
    try:
        if (args.resume or args.report) and args.rounds is not None:
            raise ValueError('Cannot replace saved rounds.')
        if args.report:
            with run_state.locked(args.report):
                report(args.report, load_batch(args.report))
            print(f"Comparison: {args.report / 'comparison.md'}")
            return 0
        if args.resume:
            folder = args.resume.resolve()
            manifest = load_batch(folder)
        else:
            cases = evaluation.load_cases()
            if not args.case and not args.all:
                for case in cases:
                    print(f"{case['id']}: {case['category']}")
                print('Select --case ID or --all to run. Each case uses 5 calls at one round.')
                return 0
            selected = set(args.case or [c['id'] for c in cases])
            if selected - {c['id'] for c in cases}:
                raise ValueError('Unknown case ID. Run without arguments to list cases.')
            folder = agora.ROOT / 'runs' / ('evaluation-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
            manifest = create_batch(folder, [c for c in cases if c['id'] in selected], args.rounds or 1)
        print(f'Evaluation directory: {folder}', flush=True)
        saved = records(folder, manifest)
        if all(r and r['status'] == 'completed' for r in saved.values()):
            with run_state.locked(folder):
                report(folder, manifest)
        else:
            with tempfile.TemporaryDirectory(prefix='agora-evaluation-') as isolated:
                providers = {name: agora.Provider(name, isolated) for name in ('codex', 'claude')}
                run_batch(folder, providers, args.timeout, args.deadline)
        print(f"Comparison: {folder / 'comparison.md'}")
        return 0
    except (agora.AgoraError, run_state.StateError, OSError, ValueError, KeyboardInterrupt) as exc:
        print(f'Stopped: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
