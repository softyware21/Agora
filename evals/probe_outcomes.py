"""Show what citation checks can and cannot establish, without model calls."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import automatic
import issues


def probe(label, invalid_quote=False):
    turns = [
        {'provider': 'codex', 'phase': 'initial', 'round': 0, 'text': 'Review the prerequisite.'},
        {'provider': 'claude', 'phase': 'initial', 'round': 0, 'text': 'Review the prerequisite.'},
        {'provider': 'codex', 'phase': 'review', 'round': 1, 'text': 'Proceed now; the prerequisite is satisfied.'},
        {'provider': 'claude', 'phase': 'review', 'round': 1, 'text': 'Do not proceed; the prerequisite is not satisfied.'},
    ]
    assessment = [{
        'topic': 'Whether the prerequisite is satisfied', 'status': label,
        'reason': 'Synthetic summary label under inspection.',
        'next_step': 'Resolve the opposing prerequisite claims.',
        'positions': [
            {'turn_id': 'T003', 'position': 'Proceed now', 'quote': turns[2]['text']},
            {'turn_id': 'T004', 'position': 'Do not proceed',
             'quote': 'Both support proceeding.' if invalid_quote else turns[3]['text']},
        ],
    }]
    turns.append({'provider': 'codex', 'phase': 'summary', 'round': 1,
                  'text': '```agora-issues\n' + json.dumps(assessment) + '\n```'})
    board = issues.ledger(turns)
    reason, _ = automatic.assess({'rounds': 1, 'issue_outcomes': board},
                                 {'target_round': 2, 'previous': ''})
    return {'reported_label': label, 'invalid_quote': invalid_quote,
            'retained_status': board['issues'][0]['status'],
            'positions': [p['position'] for p in board['issues'][0]['positions']],
            'automatic_reason': reason}


if __name__ == '__main__':
    print(json.dumps({'note': 'Diagnostic counterexamples, not a semantic validator.',
                      'cases': [probe('disputed'), probe('insufficient_information'),
                                probe('agreed'), probe('agreed', True)]}, indent=2))
