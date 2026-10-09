"""Requested models and summary routing, independent of account availability."""
import re


def model_id(value):
    if value is not None and (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', value)):
        raise ValueError('Use a model ID or alias of at most 128 letters, digits, dots, underscores, or hyphens.')
    return value


def validate(selection):
    if selection is None:
        return {'codex': None, 'claude': None, 'summary_provider': 'codex', 'summary_model': None}
    if not isinstance(selection, dict) or set(selection) != {'codex', 'claude', 'summary_provider', 'summary_model'}:
        raise ValueError('Invalid model selection.')
    if selection['summary_provider'] not in ('codex', 'claude'):
        raise ValueError('Summary provider must be codex or claude.')
    for key in ('codex', 'claude', 'summary_model'):
        model_id(selection[key])
    return dict(selection)


def target(selection, provider, phase):
    settings = validate(selection)
    return (settings['summary_model'] or settings[provider]) if phase == 'summary' else settings[provider]


def add_arguments(parser):
    parser.add_argument('--codex-model', help='Codex participant model ID; default uses the CLI default')
    parser.add_argument('--claude-model', help='Claude participant model ID or alias; default uses the CLI default')
    parser.add_argument('--summary-provider', choices=('codex', 'claude'), help='Summary provider (default: codex)')
    parser.add_argument('--summary-model', help='Summary model; default follows the chosen participant model')


def supplied(args):
    return any(getattr(args, key) is not None for key in ('codex_model', 'claude_model', 'summary_provider', 'summary_model'))


def from_args(args, base=None):
    settings = validate(base)
    if args.summary_provider is not None and args.summary_provider != settings['summary_provider']:
        settings['summary_model'] = None
    for key in settings:
        value = getattr(args, key if key not in ('codex', 'claude') else key + '_model')
        if value is not None:
            settings[key] = None if value == 'default' and key != 'summary_provider' else value
    return validate(settings)


def describe(selection):
    settings = validate(selection)
    summary = settings['summary_provider']
    return (f"Models: codex={settings['codex'] or 'CLI default'}, claude={settings['claude'] or 'CLI default'}; "
            f"summary={summary}/{target(settings, summary, 'summary') or 'CLI default'}")
