
# vw_cleaner_cli.py
import argparse
from vw_cleaner_core import clean_vault, DEFAULT_INPUT, DEFAULT_OUTPUT, DEFAULT_DELETED

def main():
    parser = argparse.ArgumentParser(description="Pulisce e deduplica export JSON di Bitwarden/Vaultwarden.")
    parser.add_argument("input_file", nargs="?", help="Il file JSON da processare")
    parser.add_argument("-o", "--output", help="Nome file di output (opzionale)")
    parser.add_argument("-d", "--deleted", help="Nome file elementi cancellati (opzionale)")
    args = parser.parse_args()

    if args.input_file:
        # modalità batch
        stats = clean_vault(
            input_file=args.input_file,
            output_file=args.output,
            deleted_file=args.deleted,
            log_cb=print,
        )
        return 0

    # modalità interattiva (se la vuoi mantenere)
    input_file = input(f"Nome file input [{DEFAULT_INPUT}]: ").strip() or DEFAULT_INPUT
    out_file = input(f"Nome file output [{DEFAULT_OUTPUT}]: ").strip() or DEFAULT_OUTPUT
    del_file = input(f"Nome file deleted [{DEFAULT_DELETED}]: ").strip() or DEFAULT_DELETED
    stats = clean_vault(input_file=input_file, output_file=out_file, deleted_file=del_file, log_cb=print)
    return 0

ifif __name__ == "__main__":
