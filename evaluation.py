"""Fixed-answer checks; prose and source reliability still need human review."""
from fractions import Fraction
import json
from pathlib import Path
import re

from evidence import unique_fields

VERSION = 1
CASE_FILE = Path(__file__).resolve().parent / 'evals' / 'cases.json'


def number(value):
    if (not isinstance(value, str) or len(value) > 80
            or not re.fullmatch(r'-?(?:\d+(?:\.\d+)?|\d+/[1-9]\d*)', value)):
        raise ValueError('Expected a bounded decimal or fraction string.')
    return Fraction(value)


def valid_value(value, kind):
    if not isinstance(value, str):
        return False
    if isinstance(kind, list):
        return value in kind
    if kind == 'number_or_unknown' and value == 'unknown':
        return True
    try:
        number(value)
        return True
    except ValueError:
        return False


def validate_cases(cases):
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise ValueError('Expected 1-100 evaluation cases.')
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError('Invalid evaluation case.')
        identifier = case.get('id')
        if (not isinstance(identifier, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', identifier)
                or identifier in seen):
            raise ValueError('Case IDs must be unique path-safe names.')
        seen.add(identifier)
        for key in ('question', 'category', 'rationale'):
            if not isinstance(case.get(key), str) or not 1 <= len(case[key]) <= 12000:
                raise ValueError(f'Invalid case {key}.')
        fields, expected = case.get('fields'), case.get('expected')
        if (not isinstance(fields, dict) or not 1 <= len(fields) <= 10
                or not isinstance(expected, dict) or fields.keys() != expected.keys()):
            raise ValueError('Expected answers must cover every field.')
        for key, kind in fields.items():
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,39}', key):
                raise ValueError('Invalid answer field name.')
            if isinstance(kind, list):
                if (not 2 <= len(kind) <= 10 or not all(isinstance(v, str) and 1 <= len(v) <= 80 for v in kind)
                        or len(set(kind)) != len(kind)):
                    raise ValueError('Invalid answer choices.')
            elif kind not in ('number', 'number_or_unknown'):
                raise ValueError('Unsupported answer type.')
            if not valid_value(expected[key], kind):
                raise ValueError('Invalid expected answer.')
    return cases


def load_cases(suite='basic'):
    if suite not in ('basic', 'challenge'):
        raise ValueError('Unknown evaluation suite.')
    path = CASE_FILE if suite == 'basic' else CASE_FILE.with_name('challenge.json')
    return validate_cases(json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_fields))


def rules(case):
    # Only the answer contract is visible to participants, never the key or rationale.
    return ('Answer in English. Explain your conclusion briefly. In every answer, including the final '
            'summary, append exactly one fenced agora-evaluation JSON object. Use exactly these fields '
            'with string values: ' + json.dumps(case['fields'], sort_keys=True)
            + '. Lists specify allowed choices. number means an exact decimal or fraction string; '
            'number_or_unknown also permits unknown when the supplied facts do not determine a value. '
            'This block is additional to the evidence blocks. Do not inspect files or look for answer keys.')


def grade(text, case):
    if text is None:
        return {'status': 'pending', 'fields': {}}
    matches = re.findall(r'^```agora-evaluation[ \t]*\r?\n(.*?)^```[ \t]*\r?$',
                         text, re.MULTILINE | re.DOTALL)
    try:
        if len(matches) != 1 or text.count('```agora-evaluation') != 1:
            raise ValueError('Expected exactly one answer block.')
        answer = json.loads(matches[0], object_pairs_hook=unique_fields)
        if not isinstance(answer, dict) or answer.keys() != case['fields'].keys():
            raise ValueError('Answer fields do not match the contract.')
        if not all(valid_value(answer[key], kind) for key, kind in case['fields'].items()):
            raise ValueError('Invalid answer value or type.')
    except (ValueError, RecursionError) as exc:
        return {'status': 'format_error', 'fields': {}, 'reason': str(exc)}
    fields = {}
    for key, kind in case['fields'].items():
        actual, expected = answer[key], case['expected'][key]
        equal = actual == expected
        if not isinstance(kind, list) and actual != 'unknown' and expected != 'unknown':
            equal = number(actual) == number(expected)
        fields[key] = {'actual': actual, 'expected': expected, 'correct': equal}
    return {'status': 'pass' if all(f['correct'] for f in fields.values()) else 'fail', 'fields': fields}


def compare(record, case):
    turns = record['turns'] if record else []
    answers = {name: next((t['text'] for t in turns if t['phase'] == 'initial' and t['provider'] == name), None)
               for name in ('codex', 'claude')}
    answers['debate'] = next((t['text'] for t in turns if t['phase'] == 'summary'), None)
    return {name: grade(text, case) for name, text in answers.items()}
