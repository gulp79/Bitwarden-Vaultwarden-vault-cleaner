"""
CLI avanzato per Bitwarden/Vaultwarden Vault Cleaner.

Supporta:
- Livelli di normalizzazione configurabili
- Politiche di merge (strict/lenient/empty_only)
- Dry-run mode con preview
- Explain mode con decision log
- Summary esteso
- Backward compatibility con versione originale

Usage:
    # Default (conservativo, compatibile con versione originale)
    python vw_cleaner_cli_v2.py input.json
    
    # Strict mode (richiede URI condivise)
    python vw_cleaner_cli_v2.py input.json --merge-policy=strict
    
    # Dry run (anteprima senza modifiche)
    python vw_cleaner_cli_v2.py input.json --dry-run
    
    # Explain mode (genera decision log)
    python vw_cleaner_cli_v2.py input.json --explain
    
    # Normalizzazione avanzata
    python vw_cleaner_cli_v2.py input.json --normalize=std

Author: Principal Engineer Review
Date: 2026-01-29
"""

import argparse
import sys
from pathlib import Path

from vw_cleaner_core_v2 import (
    clean_vault_advanced,
    CleanerConfig,
    MergePolicy,
    ConflictResolution,
)
from vw_normalization import NormalizationLevel


def create_parser() -> argparse.ArgumentParser:
    """Crea e configura il parser degli argomenti CLI."""
    
    parser = argparse.ArgumentParser(
        prog="vw_cleaner",
        description="Bitwarden/Vaultwarden Vault Cleaner - Deduplica conservativa con configurazione avanzata",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (default conservativo)
  %(prog)s bitwarden_export.json
  
  # Strict mode (richiede almeno 1 URI condivisa)
  %(prog)s input.json --merge-policy=strict
  
  # Dry run (anteprima senza scrivere file)
  %(prog)s input.json --dry-run --summary
  
  # Full explainability
  %(prog)s input.json --explain --summary
  
  # Normalizzazione standard (case-insensitive username, query string sorting)
  %(prog)s input.json --normalize=std
  
Note importanti:
  • SEMPRE lavorare su una COPIA del vault export
  • Il file 'deleted' contiene credenziali in chiaro - eliminarlo dopo verifica
  • Default settings sono CONSERVATIVI (zero rischio falsi merge)
  • Usare --dry-run la prima volta per verificare il comportamento
        """
    )
    
    # === POSITIONAL ARGUMENTS ===
    parser.add_argument(
        "input_file",
        nargs="?",
        help="File JSON di input (export Bitwarden/Vaultwarden)"
    )
    
    # === OUTPUT FILES ===
    output_group = parser.add_argument_group("output files")
    output_group.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="File JSON di output (default: bitwarden_cleaned_YYYYMMDD.json)"
    )
    output_group.add_argument(
        "-d", "--deleted",
        metavar="FILE",
        help="File JSON con item eliminati (default: bitwarden_deleted_YYYYMMDD.json)"
    )
    output_group.add_argument(
        "-l", "--log",
        metavar="FILE",
        help="File di log testuale (default: merge_log_YYYYMMDD.txt)"
    )
    
    # === NORMALIZATION ===
    norm_group = parser.add_argument_group("normalization")
    norm_group.add_argument(
        "--normalize",
        choices=["none", "min", "std", "aggressive"],
        default="min",
        help="""Livello di normalizzazione (default: min)
            none        = Match esatto, nessuna normalizzazione
            min         = Trim whitespace, lowercase hostname URI (CONSERVATIVO)
            std         = + case-insensitive username, query string sorting
            aggressive  = + eTLD+1 riduzione (NON RACCOMANDATO - falsi positivi!)
        """
    )
    
    # === MERGE POLICY ===
    policy_group = parser.add_argument_group("merge policy")
    policy_group.add_argument(
        "--merge-policy",
        choices=["lenient", "strict", "empty_only"],
        default="lenient",
        help="""Politica di merge (default: lenient)
            lenient    = Merge se URI condivise O se almeno uno ha URI vuote (originale)
            strict     = Richiede almeno 1 URI condivisa (raccomandato per sicurezza)
            empty_only = Merge solo se almeno uno ha URI vuote
        """
    )
    policy_group.add_argument(
        "--require-shared-uri",
        action="store_true",
        help="Alias per --merge-policy=strict (richiede URI condivise)"
    )
    
    # === BEHAVIOR ===
    behavior_group = parser.add_argument_group("behavior")
    behavior_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Esegui senza scrivere file (solo simulazione)"
    )
    behavior_group.add_argument(
        "--explain",
        action="store_true",
        help="Genera decision log JSON con motivazioni per ogni merge"
    )
    behavior_group.add_argument(
        "--summary",
        action="store_true",
        help="Mostra summary esteso con metriche dettagliate"
    )
    behavior_group.add_argument(
        "--quiet",
        action="store_true",
        help="Modalità silenziosa (solo errori)"
    )
    behavior_group.add_argument(
        "--preserve-metadata",
        action="store_true",
        help="Preserva metadati slave (favorite, folderId) quando possibile"
    )
    
    # === ADVANCED ===
    advanced_group = parser.add_argument_group("advanced")
    advanced_group.add_argument(
        "--notes-separator",
        default="\n\n--- MERGED NOTES ---\n",
        help="Separatore custom per note mergiate (default: '\\n\\n--- MERGED NOTES ---\\n')"
    )
    advanced_group.add_argument(
        "--decision-log",
        metavar="FILE",
        help="Path custom per decision log (se --explain attivo)"
    )
    
    # === INFO ===
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2.0.0 (Advanced Edition)"
    )
    
    return parser


def validate_args(args) -> bool:
    """
    Valida gli argomenti e ritorna True se validi.
    Stampa errori su stderr se invalidi.
    """
    if not args.input_file:
        print("ERROR: Input file richiesto", file=sys.stderr)
        print("Usa --help per vedere i dettagli", file=sys.stderr)
        return False
    
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"ERROR: File di input non trovato: {args.input_file}", file=sys.stderr)
        return False
    
    if not input_path.is_file():
        print(f"ERROR: Input non è un file: {args.input_file}", file=sys.stderr)
        return False
    
    if not input_path.suffix.lower() == ".json":
        print(f"WARNING: Il file non ha estensione .json: {args.input_file}", file=sys.stderr)
        print("Continuo comunque...", file=sys.stderr)
    
    return True


def interactive_mode():
    """
    Modalità interattiva (backward compatibility con versione originale).
    """
    print("=== Bitwarden/Vaultwarden Vault Cleaner (Interactive) ===")
    print()
    
    input_file = input("Nome file input [bitwarden_export_file.json]: ").strip()
    if not input_file:
        input_file = "bitwarden_export_file.json"
    
    output_file = input("Nome file output [bitwarden_cleaned_YYYYMMDD.json]: ").strip()
    if not output_file:
        output_file = None
    
    deleted_file = input("Nome file deleted [bitwarden_deleted_YYYYMMDD.json]: ").strip()
    if not deleted_file:
        deleted_file = None
    
    print()
    print("Vuoi usare modalità STRICT (richiede URI condivise)? [y/N]: ", end="")
    strict = input().strip().lower() in ('y', 'yes', 's', 'si')
    
    print()
    print(f"Input:  {input_file}")
    print(f"Output: {output_file or '(default)'}")
    print(f"Policy: {'STRICT' if strict else 'LENIENT (default)'}")
    print()
    print("Procedo? [Y/n]: ", end="")
    confirm = input().strip().lower()
    if confirm in ('n', 'no'):
        print("Annullato.")
        return 1
    
    # Crea config
    config = CleanerConfig(
        merge_policy=MergePolicy.STRICT if strict else MergePolicy.LENIENT,
        enable_explain=False,
        enable_dry_run=False,
    )
    
    # Esegui
    try:
        stats = clean_vault_advanced(
            input_file=input_file,
            output_file=output_file,
            deleted_file=deleted_file,
            config=config,
            log_cb=print,
        )
        
        print()
        print(stats.summary_text())
        return 0
    
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 1


def main():
    """Entry point principale."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Modalità interattiva se nessun argomento
    if not args.input_file:
        return interactive_mode()
    
    # Valida argomenti
    if not validate_args(args):
        return 1
    
    # Costruisci configurazione
    try:
        normalization_level = NormalizationLevel(args.normalize)
    except ValueError:
        print(f"ERROR: Livello normalizzazione non valido: {args.normalize}", file=sys.stderr)
        return 1
    
    try:
        merge_policy = MergePolicy(args.merge_policy)
    except ValueError:
        print(f"ERROR: Politica merge non valida: {args.merge_policy}", file=sys.stderr)
        return 1
    
    # Forza STRICT se --require-shared-uri
    if args.require_shared_uri:
        merge_policy = MergePolicy.STRICT
    
    config = CleanerConfig(
        normalization_level=normalization_level,
        merge_policy=merge_policy,
        require_shared_uri=args.require_shared_uri,
        preserve_all_metadata=args.preserve_metadata,
        enable_explain=args.explain,
        enable_dry_run=args.dry_run,
        notes_separator=args.notes_separator,
    )
    
    # Setup logger
    def log_callback(msg: str):
        if not args.quiet:
            print(msg)
    
    # Esegui pulizia
    try:
        if not args.quiet:
            print("=== Bitwarden/Vaultwarden Vault Cleaner (Advanced) ===")
            print(f"Input:          {args.input_file}")
            print(f"Normalization:  {args.normalize}")
            print(f"Merge policy:   {merge_policy.value}")
            print(f"Dry run:        {'YES' if args.dry_run else 'NO'}")
            print(f"Explain:        {'YES' if args.explain else 'NO'}")
            print()
        
        stats = clean_vault_advanced(
            input_file=args.input_file,
            output_file=args.output,
            deleted_file=args.deleted,
            log_file=args.log,
            decision_log_file=args.decision_log,
            config=config,
            log_cb=log_callback,
        )
        
        # Summary
        if args.summary or not args.quiet:
            print()
            print(stats.summary_text())
        
        # Warnings
        if not args.quiet:
            if stats.removed > 0:
                print()
                print("⚠️  IMPORTANTE:")
                print(f"   - {stats.removed} item rimossi salvati in: {stats.deleted_file}")
                print("   - Il file contiene credenziali in chiaro")
                print("   - VERIFICA il risultato e poi ELIMINA il file deleted")
            
            if args.dry_run:
                print()
                print("ℹ️  Dry run completato - nessun file modificato")
                print("   Rimuovi --dry-run per applicare le modifiche")
        
        return 0
    
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: Errore imprevisto: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
