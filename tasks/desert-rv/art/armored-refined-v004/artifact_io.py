"""Output isolation guard. Never mix this generation with an earlier run's files."""
from pathlib import Path

def fresh_output(path):
    path=Path(path).resolve()
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError('Refusing nonempty or non-directory output: '+str(path))
    path.mkdir(parents=True,exist_ok=True)
    return path
