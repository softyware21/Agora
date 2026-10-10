"""Store the user's decision separately from model-visible discussion records."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

import run_state

FIELDS = ('decision', 'reason', 'open_questions')


def path_for(folder):
    folder = Path(folder).resolve()
    path = folder / 'judgment.json'
    if path.resolve().parent != folder or path.is_symlink():
        raise ValueError('Decision notes must stay inside the discussion directory.')
    return path


def load(folder):
    with run_state.io_lock:
        path = path_for(folder)
        if not path.exists():
            return dict(revision=0, updated_at=None, **{key: '' for key in FIELDS})
        if path.stat().st_size > 100000:
            raise ValueError('Decision notes are too large to read.')
        data = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(data, dict) or type(data.get('revision')) is not int
                or data['revision'] < 1 or any(not isinstance(data.get(key), str)
                or len(data[key]) > 4000 for key in FIELDS)):
            raise ValueError('Decision notes could not be read. Keep the original file.')
        return data


def save(folder, payload):
    if (type(payload.get('revision')) is not int or any(not isinstance(payload.get(key), str)
            or len(payload[key]) > 4000 for key in FIELDS)):
        raise ValueError('Each decision field must contain at most 4,000 characters.')
    folder = Path(folder).resolve()
    lock_folder = folder / '.judgment-state'
    if lock_folder.resolve().parent != folder or lock_folder.is_symlink():
        raise ValueError('Decision notes must stay inside the discussion directory.')
    with run_state.io_lock, run_state.locked(lock_folder):
        current = load(folder)
        if current['revision'] != payload['revision']:
            raise ValueError('Decision notes changed in another window. Reopen the discussion before saving.')
        data = {key: payload[key] for key in FIELDS}
        data.update(revision=current['revision'] + 1, updated_at=datetime.now(timezone.utc).isoformat())
        destination = path_for(folder)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=folder,
                                         prefix='judgment-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
        try:
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return data
