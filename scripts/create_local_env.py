"""Cria segredos exclusivos de desenvolvimento sem exibi-los ou sobrescrevê-los."""

import argparse
import base64
import os
from pathlib import Path
import secrets


ROOT = Path(__file__).resolve().parent.parent


def create_local_env(output):
    template = (ROOT / '.env.example').read_text(encoding='utf-8')
    replacements = {
        'GERAR_CHAVE_DJANGO': secrets.token_urlsafe(50),
        'GERAR_CHAVE_CRIPTOGRAFIA': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'GERAR_CHAVE_HASH': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'GERAR_SENHA_POSTGRES': secrets.token_urlsafe(32),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    # O_EXCL recusa inclusive links simbólicos preexistentes; 0600 restringe acesso no Unix.
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as env_file:
        env_file.write(template)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.env')
    args = parser.parse_args()
    try:
        create_local_env(args.output)
    except FileExistsError:
        parser.exit(1, 'Arquivo já existe; nenhuma chave foi alterada.\n')
    print('Configuração local criada. Guarde as chaves para continuar lendo o banco de demonstração.')


if __name__ == '__main__':
    main()
