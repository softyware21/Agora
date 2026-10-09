"""Check declared calculations; leave prose and external facts unverified."""
import json
import re

from calculator import calculate, CalculationError, VERSION

DECLARATIONS = re.compile(r'^```agora-calculations[ \t]*\r?\n(.*?)^```[ \t]*\r?$', re.MULTILINE | re.DOTALL)
NUMBER = r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)'
EXPECTED = re.compile(rf'{NUMBER}(?:\s*/\s*{NUMBER})?\Z')


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate field.')
        result[key] = value
    return result


def check_answer(text, turn_number):
    result = {'calculator_version': VERSION, 'status': 'not_declared', 'checks': [], 'warnings': []}
    blocks = DECLARATIONS.findall(text)
    if not blocks and '```agora-calculations' not in text:
        return result
    if len(blocks) != 1 or text.count('```agora-calculations') != 1:
        result.update(status='invalid', warnings=['Expected one closed calculation block.'])
        return result
    try:
        claims = json.loads(blocks[0], object_pairs_hook=unique_fields)
    except (ValueError, RecursionError):
        result.update(status='invalid', warnings=['Calculation block is not valid JSON.'])
        return result
    if not isinstance(claims, list) or len(claims) > 10:
        result.update(status='invalid', warnings=['Calculation block must contain at most 10 entries.'])
        return result
    result['status'] = 'parsed'
    for index, claim in enumerate(claims, 1):
        check = {'id': f'T{turn_number:03d}-C{index:02d}', 'status': 'unverified',
                 'scope': 'arithmetic_only', 'claim': '', 'expression': '', 'expected': '',
                 'unit': '', 'actual': None, 'reason': None}
        result['checks'].append(check)
        if not isinstance(claim, dict):
            check['reason'] = 'Calculation entry must be an object.'
            continue
        limits = {'claim': 500, 'expression': 256, 'expected': 256, 'unit': 80}
        valid = True
        for key, limit in limits.items():
            value = claim.get(key, '' if key == 'unit' else None)
            if not isinstance(value, str) or len(value) > limit or (key != 'unit' and not value.strip()):
                valid = False
            else:
                check[key] = value.strip()
        if not valid:
            check['reason'] = 'Claim, expression, and expected value must be bounded strings.'
            continue
        try:
            if not EXPECTED.fullmatch(check['expected']):
                raise CalculationError('Expected value must be a decimal number or a fraction.')
            expected = calculate(check['expected'])
            actual = calculate(check['expression'])
            check['actual'] = str(actual)
            check['status'] = 'arithmetic_match' if actual == expected else 'arithmetic_mismatch'
            check['reason'] = 'Inputs, units, and the surrounding claim have not been verified.'
        except CalculationError as exc:
            check['reason'] = str(exc)
    return result


def ledger(turns):
    entries = []
    for number, turn in enumerate(turns, 1):
        entry = check_answer(turn['text'], number)
        entry.update(turn=number, provider=turn['provider'], phase=turn['phase'], round=turn['round'])
        entries.append(entry)
    return entries
