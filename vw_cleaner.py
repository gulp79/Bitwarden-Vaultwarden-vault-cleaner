import json
import os
import shutil
import datetime
import logging
import argparse
import sys
from urllib.parse import urlsplit

# ------------------------------------------------------------------------
# CONFIGURAZIONE GLOBALE
# ------------------------------------------------------------------------
DATE_SUFFIX = datetime.datetime.now().strftime("%Y%m%d")
DEFAULT_INPUT = "bitwarden_export_file.json"

# Nomi di default con data (usati se l'utente non specifica altro)
DEFAULT_OUTPUT = f"bitwarden_cleaned_{DATE_SUFFIX}.json"
DEFAULT_DELETED = f"bitwarden_deleted_{DATE_SUFFIX}.json"
LOG_FILE = f"merge_log_{DATE_SUFFIX}.txt"

# Configurazione Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.info

# ------------------------------------------------------------------------
# FUNZIONI DI UTILITÀ
# ------------------------------------------------------------------------

def normalize_uri(uri_str):
    """Normalizza un URI: rimuove spazi, lowercase, via slash finale."""
    if not uri_str:
        return ""
    return uri_str.strip().lower().rstrip('/')

def create_backup(filename):
    """Crea una copia .bak con timestamp del file originale."""
    if os.path.exists(filename):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{filename}.{timestamp}.bak"
        shutil.copy2(filename, backup_name)
        log(f"Backup di sicurezza creato: {backup_name}")
    else:
        log(f"ERRORE FATALE: File di input '{filename}' non trovato.")
        sys.exit(1)

def merge_items(master, slave):
    """Logica di unione (Merge) conservativa."""
    # 1. Merge URIs
    master_uris = {normalize_uri(u['uri']) for u in master['login'].get('uris', []) if u.get('uri')}
    slave_uris_list = slave['login'].get('uris') or []
    
    for u in slave_uris_list:
        u_str = u.get('uri')
        if u_str and normalize_uri(u_str) not in master_uris:
            if 'uris' not in master['login'] or master['login']['uris'] is None:
                master['login']['uris'] = []
            master['login']['uris'].append(u)
            master_uris.add(normalize_uri(u_str))
    
    # 2. Merge Notes
    if slave.get('notes') and slave['notes'] != master.get('notes'):
        current_notes = master.get('notes', "")
        if current_notes:
            master['notes'] = current_notes + "\n\n--- MERGED NOTES ---\n" + slave['notes']
        else:
            master['notes'] = slave['notes']

    # 3. Merge TOTP (Master vince, slave riempie se vuoto)
    if not master['login'].get('totp') and slave['login'].get('totp'):
        master['login']['totp'] = slave['login'].get('totp')

    return master

# ------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------

def main():
    # Parsing argomenti da riga di comando
    parser = argparse.ArgumentParser(description="Pulisce e deduplica export JSON di Bitwarden/Vaultwarden.")
    
    parser.add_argument("input_file", nargs='?', help="Il file JSON da processare")
    parser.add_argument("-o", "--output", help="Nome file di output (opzionale)")
    parser.add_argument("-d", "--deleted", help="Nome file elementi cancellati (opzionale)")
    
    args = parser.parse_args()

    log("=== Bitwarden/Vaultwarden Cleaner v3.0 ===")

    # Logica per determinare i nomi dei file (Interattivo vs CLI)
    if args.input_file:
        # Modalità CLI (Non interattiva)
        input_filename = args.input_file
        output_filename = args.output if args.output else DEFAULT_OUTPUT
        deleted_filename = args.deleted if args.deleted else DEFAULT_DELETED
        interactive_mode = False
        log(f"Modalità Batch attiva.")
        log(f"Input: {input_filename} | Output: {output_filename}")
    else:
        # Modalità Interattiva (chiede all'utente)
        interactive_mode = True
        raw_input = input(f"Nome file input [{DEFAULT_INPUT}]: ").strip()
        input_filename = raw_input if raw_input else DEFAULT_INPUT
        # Qui impostiamo i default, verranno confermati alla fine
        output_filename = DEFAULT_OUTPUT
        deleted_filename = DEFAULT_DELETED

    # 1. Backup e Caricamento
    create_backup(input_filename)
    
    with open(input_filename, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            log("ERRORE: Il file non è un JSON valido.")
            sys.exit(1)

    items = data.get('items', [])
    total_items = len(items)
    log(f"Caricati {total_items} elementi.")

    # 2. Raggruppamento
    grouped_logins = {}
    kept_items = []
    deleted_items_list = []
    
    for item in items:
        # Skip non-login o cestino
        if item.get('type') != 1:
            kept_items.append(item)
            continue
        
        login = item.get('login', {})
        username = login.get('username')
        password = login.get('password')

        if not username or not password:
            kept_items.append(item)
            continue

        key = (username, password)
        if key not in grouped_logins:
            grouped_logins[key] = []
        grouped_logins[key].append(item)

    # 3. Deduplicazione
    merges_count = 0
    
    for (user, pwd), group in grouped_logins.items():
        if len(group) == 1:
            kept_items.append(group[0])
            continue
        
        # Ordina per data (il più recente è master)
        group.sort(key=lambda x: x.get('revisionDate', ''), reverse=True)
        master = group[0]
        master_uri_set = {normalize_uri(u['uri']) for u in master['login'].get('uris', []) if u.get('uri')}
        merged_something = False

        for i in range(1, len(group)):
            candidate = group[i]
            candidate_uris = {normalize_uri(u['uri']) for u in candidate['login'].get('uris', []) if u.get('uri')}
            
            # Condizione: URI comune OR uno dei due senza URI
            should_merge = (
                not master_uri_set or 
                not candidate_uris or 
                not master_uri_set.isdisjoint(candidate_uris)
            )

            if should_merge:
                master = merge_items(master, candidate)
                new_uris = {normalize_uri(u['uri']) for u in master['login'].get('uris', []) if u.get('uri')}
                master_uri_set.update(new_uris)
                
                candidate['reasonForDeletion'] = f"Merged into '{master.get('name')}' (Id: {master.get('id')})"
                deleted_items_list.append(candidate)
                merged_something = True
                merges_count += 1
            else:
                kept_items.append(candidate)
        
        kept_items.append(master)
        if merged_something:
            log(f"Uniti elementi per user '{user}': Master '{master.get('name')}'")

    # 4. Salvataggio
    data['items'] = kept_items
    
    # Se siamo in modalità interattiva, chiediamo conferma finale dei nomi (opzionale)
    if interactive_mode:
        raw_out = input(f"Nome file output [{output_filename}]: ").strip()
        if raw_out: output_filename = raw_out
        
        # In interactive, usiamo il nome deleted basato sull'output scelto
        # o manteniamo quello calcolato? Manteniamo coerenza.
        # Se l'utente non ha chiesto custom, usiamo i default calcolati.

    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    with open(deleted_filename, 'w', encoding='utf-8') as f:
        json.dump(deleted_items_list, f, indent=2, ensure_ascii=False)

    log("=== Operazione Completata ===")
    log(f"Totale Inizio: {total_items} | Totale Fine: {len(kept_items)}")
    log(f"Duplicati rimossi: {len(deleted_items_list)}")
    log(f"File salvati: {output_filename}, {deleted_filename}")

if __name__ == "__main__":
    main()