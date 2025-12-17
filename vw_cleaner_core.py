
# vw_cleaner_core.py
import json, os, shutil, datetime
from typing import Callable, Optional, Tuple, Dict, Any, List

DATE_SUFFIX = datetime.datetime.now().strftime("%Y%m%d")
DEFAULT_INPUT = "bitwarden_export_file.json"
DEFAULT_OUTPUT = f"bitwarden_cleaned_{DATE_SUFFIX}.json"
DEFAULT_DELETED = f"bitwarden_deleted_{DATE_SUFFIX}.json"
DEFAULT_LOGFILE = f"merge_log_{DATE_SUFFIX}.txt"

def normalize_uri(uri_str: str) -> str:
    if not uri_str:
        return ""
    return uri_str.strip().lower().rstrip("/")

def create_backup(filename: str, log_cb: Optional[Callable[[str], None]] = None) -> str:
    if not os.path.exists(filename):
        raise FileNotFoundError(f"File di input '{filename}' non trovato.")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{filename}.{timestamp}.bak"
    shutil.copy2(filename, backup_name)
    if log_cb:
        log_cb(f"Backup di sicurezza creato: {backup_name}")
    return backup_name

def merge_items(master: dict, slave: dict) -> dict:
    # 1) URIs
    master_uris = {normalize_uri(u.get("uri")) for u in master["login"].get("uris", []) if u.get("uri")}
    for u in (slave["login"].get("uris") or []):
        u_str = u.get("uri")
        if u_str and normalize_uri(u_str) not in master_uris:
            master["login"].setdefault("uris", [])
            master["login"]["uris"].append(u)
            master_uris.add(normalize_uri(u_str))

    # 2) Notes
    if slave.get("notes") and slave.get("notes") != master.get("notes"):
        current = master.get("notes", "")
        if current:
            master["notes"] = current + "\n\n--- MERGED NOTES ---\n" + slave["notes"]
        else:
            master["notes"] = slave["notes"]

    # 3) TOTP (se master vuoto)
    if not master["login"].get("totp") and slave["login"].get("totp"):
        master["login"]["totp"] = slave["login"]["totp"]

    return master

def clean_vault(
    input_file: str,
    output_file: Optional[str] = None,
    deleted_file: Optional[str] = None,
    log_file: Optional[str] = None,
    log_cb: Optional[Callable[[str], None]] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    """
    Esegue pulizia + deduplica. Ritorna stats.
    """
    if output_file is None:
        output_file = DEFAULT_OUTPUT
    if deleted_file is None:
        deleted_file = DEFAULT_DELETED
    if log_file is None:
        log_file = DEFAULT_LOGFILE

    def _log(msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        # scrive anche su file log, come lo script originale
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(line + "\n")
        if log_cb:
            log_cb(line)

    _log("=== Bitwarden/Vaultwarden Cleaner (CORE) ===")
    create_backup(input_file, log_cb=_log)

    with open(input_file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            raise ValueError("Il file non è un JSON valido.")

    items = data.get("items", [])
    total_items = len(items)
    _log(f"Caricati {total_items} elementi.")
    if progress_cb:
        progress_cb(0, total_items)

    grouped_logins: Dict[Tuple[str, str], List[dict]] = {}
    kept_items: List[dict] = []
    deleted_items_list: List[dict] = []

    # Raggruppamento O(N)
    for idx, item in enumerate(items, start=1):
        if item.get("type") != 1:  # non login
            kept_items.append(item)
            continue

        login = item.get("login", {}) or {}
        username = login.get("username")
        password = login.get("password")
        if not username or not password:
            kept_items.append(item)
            continue

        key = (username, password)
        grouped_logins.setdefault(key, []).append(item)

        if progress_cb and idx % 200 == 0:
            progress_cb(idx, total_items)

    merges_count = 0

    # Deduplicazione
    for (user, pwd), group in grouped_logins.items():
        if len(group) == 1:
            kept_items.append(group[0])
            continue

        group.sort(key=lambda x: x.get("revisionDate", ""), reverse=True)
        master = group[0]
        master_uri_set = {
            normalize_uri(u.get("uri"))
            for u in master["login"].get("uris", [])
            if u.get("uri")
        }

        merged_something = False

        for i in range(1, len(group)):
            candidate = group[i]
            candidate_uris = {
                normalize_uri(u.get("uri"))
                for u in candidate["login"].get("uris", [])
                if u.get("uri")
            }

            should_merge = (
                not master_uri_set or
                not candidate_uris or
                not master_uri_set.isdisjoint(candidate_uris)
            )

            if should_merge:
                master = merge_items(master, candidate)
                master_uri_set.update({
                    normalize_uri(u.get("uri"))
                    for u in master["login"].get("uris", [])
                    if u.get("uri")
                })
                candidate["reasonForDeletion"] = f"Merged into '{master.get('name')}' (Id: {master.get('id')})"
                deleted_items_list.append(candidate)
                merges_count += 1
                merged_something = True
            else:
                kept_items.append(candidate)

        kept_items.append(master)

        if merged_something:
            _log(f"Uniti elementi per user '{user}': Master '{master.get('name')}'")

    # Salvataggio (una sola volta, veloce come il tuo script)
    data["items"] = kept_items
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    with open(deleted_file, "w", encoding="utf-8") as f:
        json.dump(deleted_items_list, f, indent=2, ensure_ascii=False)

    _log("=== Operazione Completata ===")
    _log(f"Totale Inizio: {total_items} | Totale Fine: {len(kept_items)}")
    _log(f"Duplicati rimossi: {len(deleted_items_list)}")
    _log(f"File salvati: {output_file}, {deleted_file}")
    if progress_cb:
        progress_cb(total_items, total_items)

    return {
        "total_start": total_items,
        "total_end": len(kept_items),
        "removed": len(deleted_items_list),
        "merges": merges_count,
        "output_file": output_file,
        "deleted_file": deleted_file,
        "log_file": log_file,
    }
