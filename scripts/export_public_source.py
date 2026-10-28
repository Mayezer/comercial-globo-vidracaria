"""Exporta uma cópia do código sem histórico, banco, uploads ou arquivos locais."""

import argparse
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parent.parent
ROOT_FILES = (
    '.dockerignore', '.env.example', '.gitignore', '.gitleaks.toml', 'Dockerfile', 'README.md',
    'PUBLICATION.md', 'SECURITY.md', 'SECURITY_DEPLOYMENT.md', 'docker-compose.yaml',
    'manage.py', 'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml',
    'requirements.txt', 'tsconfig.json', 'worker-configuration.d.ts', 'wrangler.jsonc',
)
SOURCE_DIRS = (
    '.github', 'accounts', 'app', 'calculator', 'categories', 'dashboard', 'docker',
    'docs', 'glazing_services', 'products', 'sales', 'scripts', 'showcase', 'src', 'static',
    'templates',
)
EXCLUDED_DIRS = {
    '.git', '.aws', '.ssh', '.codex', '.agents', '.wrangler', '__pycache__',
    'node_modules', 'venv', '.venv', 'media', 'uploads', 'backups', 'fixtures',
}
SOURCE_SUFFIXES = {'.py', '.html', '.xml', '.css', '.js', '.ts', '.sh', '.md', '.yml', '.yaml'}
# Imagens do layout revisadas; uploads nunca são incluídos.
PUBLIC_IMAGES = {
    'showcase/static/img/foto_capa_globo_vidracaria.jpg',
    'showcase/static/img/logo_globo.jpeg',
}


def source_files():
    selected = []
    for name in ROOT_FILES:
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'Arquivo obrigatório ausente ou simbólico: {name}')
        selected.append(path)
    for directory in SOURCE_DIRS:
        base = ROOT / directory
        if base.is_symlink():
            raise ValueError(f'Pasta simbólica não permitida: {directory}')
        for path in base.rglob('*'):
            relative = path.relative_to(ROOT)
            if any(part in EXCLUDED_DIRS for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError(f'Link simbólico não permitido: {relative}')
            if not path.is_file() or path.name.startswith('.'):
                continue
            if path.suffix in SOURCE_SUFFIXES or relative.as_posix() in PUBLIC_IMAGES:
                selected.append(path)
    return sorted(selected)


def export_source(output):
    files = source_files()
    output.parent.mkdir(parents=True, exist_ok=True)
    # O modo x recusa substituir uma exportação já existente.
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, 'globo-vidracaria/' + path.relative_to(ROOT).as_posix())
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--output', type=Path, default=ROOT / 'dist' / 'globo-vidracaria-publico.zip',
    )
    args = parser.parse_args()
    try:
        count = export_source(args.output)
    except (ValueError, FileExistsError) as error:
        parser.exit(1, f'Exportação recusada: {error}\n')
    print(f'Cópia criada com {count} arquivos: {args.output}')
    print('Revise o conteúdo e execute o Gitleaks antes de publicar. O histórico original não foi auditado.')


if __name__ == '__main__':
    main()
