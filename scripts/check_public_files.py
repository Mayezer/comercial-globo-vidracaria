"""Recusa arquivos de dados ou segredos rastreados pelo Git, mesmo com .gitignore."""

from pathlib import PurePosixPath
import subprocess
import sys


FORBIDDEN_DIRS = {
    '.aws', '.ssh', '.codex', '.agents', '.wrangler', 'media', 'uploads', 'backups',
    'venv', '.venv', 'node_modules', '__pycache__', 'staticfiles', 'tmp', 'dist',
}
FORBIDDEN_SUFFIXES = {
    '.sqlite', '.sqlite3', '.db', '.dump', '.sql', '.bak', '.backup', '.log',
    '.pem', '.key', '.p12', '.pfx', '.pyc', '.pyo',
}


def is_private_path(name):
    path = PurePosixPath(name)
    if any(part in FORBIDDEN_DIRS for part in path.parts):
        return True
    if name == '.env.example':
        return False
    return (
        path.name == '.env'
        or path.name.startswith(('.env.', '.dev.vars', 'credentials', 'service-account'))
        or path.suffix.lower() in FORBIDDEN_SUFFIXES
        or any(marker in path.name.lower() for marker in ('.sqlite-', '.sqlite3-', '.db-'))
    )


def main():
    result = subprocess.run(['git', 'ls-files', '-z'], capture_output=True, check=False)
    if result.returncode:
        sys.exit('Não foi possível ler os arquivos rastreados. Execute em um checkout Git.')
    paths = result.stdout.decode('utf-8', errors='surrogateescape').split('\0')
    rejected = [name for name in paths if name and is_private_path(name)]
    if rejected:
        print('Arquivos privados ou gerados rastreados pelo Git:')
        for name in rejected:
            print(f'- {name!r}')
        sys.exit(1)
    print('Nenhum caminho privado ou gerado foi encontrado entre os arquivos rastreados.')


if __name__ == '__main__':
    main()
