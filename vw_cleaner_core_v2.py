"""
Core migliorato per Bitwarden/Vaultwarden Vault Cleaner.

Miglioramenti rispetto alla versione originale:
- Determinismo garantito (stable sort)
- Idempotenza verificabile
- Normalizzazione parametrica
- Registro decisionale (explainability)
- Metriche estese
- Politiche di merge configurabili

Author: Principal Engineer Review  
Date: 2026-01-29
"""

import json
import os
import shutil
import datetime
import hashlib
from typing import Callable, Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass, field, asdict
from enum import Enum

from vw_normalization import (
    NormalizationLevel,
    generate_grouping_key,
    extract_uris_normalized,
    have_shared_uri,
    get_uri_normalizer,
)


# =============================================================================
# CONFIGURATION & ENUMS
# =============================================================================

class MergePolicy(Enum):
    """Politiche di merge per URI."""
    STRICT = "strict"      # Richiede almeno 1 URI in comune
    LENIENT = "lenient"    # Merge anche se URI disgiunte (comportamento originale)
    EMPTY_ONLY = "empty_only"  # Merge solo se almeno uno ha URI vuote


class ConflictResolution(Enum):
    """Strategia di risoluzione conflitti."""
    PREFER_MASTER = "prefer_master"  # Mantieni sempre valore del master
    PREFER_NEWER = "prefer_newer"    # Usa revisionDate per decidere
    MERGE_ALL = "merge_all"          # Unisci/concatena tutto


@dataclass
class CleanerConfig:
    """Configurazione del cleaner."""
    # Normalizzazione
    normalization_level: NormalizationLevel = NormalizationLevel.MIN
    
    # Politiche merge
    merge_policy: MergePolicy = MergePolicy.LENIENT
    conflict_resolution: ConflictResolution = ConflictResolution.PREFER_MASTER
    
    # Comportamenti
    require_shared_uri: bool = False  # Se True, forza STRICT
    preserve_all_metadata: bool = False  # Preserva anche metadati slave
    
    # Output
    enable_explain: bool = False  # Genera registro decisionale
    enable_dry_run: bool = False  # Non scrive file, solo simula
    
    # Note separator
    notes_separator: str = "\n\n--- MERGED NOTES ---\n"
    
    def __post_init__(self):
        # Enforce strict if required
        if self.require_shared_uri:
            self.merge_policy = MergePolicy.STRICT


# =============================================================================
# DECISION TRACKING
# =============================================================================

@dataclass
class MergeDecision:
    """Rappresenta una decisione di merge."""
    timestamp: str
    master_id: str
    master_name: str
    slave_id: str
    slave_name: str
    decision: str  # "merged" | "kept_separate"
    reason: str
    shared_uris: List[str] = field(default_factory=list)
    merged_fields: List[str] = field(default_factory=list)
    notes: Optional[str] = None


class DecisionLog:
    """Registro delle decisioni di merge."""
    
    def __init__(self):
        self.decisions: List[MergeDecision] = []
    
    def add_merge(self, master: dict, slave: dict, reason: str, 
                  shared_uris: List[str], merged_fields: List[str],
                  notes: Optional[str] = None):
        """Registra una decisione di merge."""
        decision = MergeDecision(
            timestamp=datetime.datetime.now().isoformat(),
            master_id=master.get("id", "unknown"),
            master_name=master.get("name", "unnamed"),
            slave_id=slave.get("id", "unknown"),
            slave_name=slave.get("name", "unnamed"),
            decision="merged",
            reason=reason,
            shared_uris=shared_uris,
            merged_fields=merged_fields,
            notes=notes,
        )
        self.decisions.append(decision)
    
    def add_kept_separate(self, item1: dict, item2: dict, reason: str):
        """Registra una decisione di NON merge."""
        decision = MergeDecision(
            timestamp=datetime.datetime.now().isoformat(),
            master_id=item1.get("id", "unknown"),
            master_name=item1.get("name", "unnamed"),
            slave_id=item2.get("id", "unknown"),
            slave_name=item2.get("name", "unnamed"),
            decision="kept_separate",
            reason=reason,
        )
        self.decisions.append(decision)
    
    def to_json(self) -> str:
        """Serializza in JSON."""
        return json.dumps(
            [asdict(d) for d in self.decisions],
            indent=2,
            ensure_ascii=False
        )
    
    def save(self, filepath: str):
        """Salva su file."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json())


# =============================================================================
# STATISTICS
# =============================================================================

@dataclass
class CleanerStats:
    """Statistiche estese dell'operazione di pulizia."""
    # Conteggi base
    total_start: int = 0
    total_end: int = 0
    removed: int = 0
    
    # Gruppi
    groups_analyzed: int = 0
    groups_merged: int = 0
    groups_kept_separate: int = 0
    
    # Merge details
    merges_count: int = 0
    uri_collisions_avoided: int = 0  # Coppie con URI disgiunte NON mergiate
    totp_preserved: int = 0
    notes_concatenated: int = 0
    
    # Performance
    processing_time_ms: int = 0
    
    # Files
    output_file: str = ""
    deleted_file: str = ""
    log_file: str = ""
    decision_log_file: str = ""
    
    def to_dict(self) -> dict:
        """Converte in dizionario."""
        return asdict(self)
    
    def summary_text(self) -> str:
        """Genera un riassunto testuale."""
        lines = [
            "=" * 60,
            "VAULT CLEANER - SUMMARY",
            "=" * 60,
            f"Total items (start):        {self.total_start}",
            f"Total items (end):          {self.total_end}",
            f"Items removed:              {self.removed}",
            f"",
            f"Groups analyzed:            {self.groups_analyzed}",
            f"Groups merged:              {self.groups_merged}",
            f"Groups kept separate:       {self.groups_kept_separate}",
            f"",
            f"Merge operations:           {self.merges_count}",
            f"URI collisions avoided:     {self.uri_collisions_avoided}",
            f"TOTP seeds preserved:       {self.totp_preserved}",
            f"Notes concatenated:         {self.notes_concatenated}",
            f"",
            f"Processing time:            {self.processing_time_ms} ms",
            f"",
            f"Output files:",
            f"  - Cleaned:  {self.output_file}",
            f"  - Deleted:  {self.deleted_file}",
            f"  - Log:      {self.log_file}",
        ]
        
        if self.decision_log_file:
            lines.append(f"  - Decisions: {self.decision_log_file}")
        
        lines.append("=" * 60)
        return "\n".join(lines)


# =============================================================================
# STABLE SORTING
# =============================================================================

def stable_sort_key(item: dict) -> Tuple:
    """
    Genera una chiave di ordinamento deterministico per la selezione del master.
    
    Criteri (in ordine):
    1. revisionDate (più recente = preferito)
    2. creationDate (più recente = preferito se revision uguale)
    3. ID (lessicografico come tie-breaker finale)
    
    Returns:
        Tupla ordinabile
    """
    revision = item.get("revisionDate", "")
    creation = item.get("creationDate", "")
    item_id = item.get("id", "")
    
    # Reverse=True nel sort, quindi usiamo valori negativi o invertiti
    return (revision, creation, item_id)


# =============================================================================
# MERGE LOGIC
# =============================================================================

def merge_items_advanced(
    master: dict,
    slave: dict,
    config: CleanerConfig,
    decision_log: Optional[DecisionLog] = None,
) -> Tuple[dict, List[str]]:
    """
    Merge avanzato di due item.
    
    Args:
        master: Item master (verrà modificato)
        slave: Item da mergiare in master
        config: Configurazione
        decision_log: Log decisionale (opzionale)
    
    Returns:
        Tupla (master_updated, merged_fields)
    """
    merged_fields = []
    
    # 1) URIs - Unione insiemistica
    uri_normalizer = get_uri_normalizer(config.normalization_level)
    master_uris_norm = {
        uri_normalizer(u.get("uri", ""))
        for u in master["login"].get("uris", [])
        if u.get("uri")
    }
    
    uris_added = 0
    for u_obj in (slave["login"].get("uris") or []):
        uri_str = u_obj.get("uri")
        if uri_str and uri_normalizer(uri_str) not in master_uris_norm:
            master["login"].setdefault("uris", [])
            master["login"]["uris"].append(u_obj)
            master_uris_norm.add(uri_normalizer(uri_str))
            uris_added += 1
    
    if uris_added > 0:
        merged_fields.append("uris")
    
    # 2) Notes - Concatenazione
    if slave.get("notes") and slave.get("notes") != master.get("notes"):
        current = master.get("notes", "")
        if current:
            master["notes"] = current + config.notes_separator + slave["notes"]
        else:
            master["notes"] = slave["notes"]
        merged_fields.append("notes")
    
    # 3) TOTP - Preservazione conservativa
    if not master["login"].get("totp") and slave["login"].get("totp"):
        master["login"]["totp"] = slave["login"]["totp"]
        merged_fields.append("totp")
    
    # 4) Metadati opzionali
    if config.preserve_all_metadata:
        # Preserva favorite se slave è favorito
        if slave.get("favorite") and not master.get("favorite"):
            master["favorite"] = True
            merged_fields.append("favorite")
        
        # Preserva folder se master non ha folder
        if slave.get("folderId") and not master.get("folderId"):
            master["folderId"] = slave["folderId"]
            merged_fields.append("folderId")
    
    return master, merged_fields


def should_merge_items(
    master: dict,
    candidate: dict,
    config: CleanerConfig,
) -> Tuple[bool, str]:
    """
    Determina se due item devono essere mergiati.
    
    Args:
        master: Item master
        candidate: Item candidato
        config: Configurazione
    
    Returns:
        Tupla (should_merge: bool, reason: str)
    """
    master_uris = extract_uris_normalized(master, config.normalization_level)
    candidate_uris = extract_uris_normalized(candidate, config.normalization_level)
    
    # Applica politica di merge
    if config.merge_policy == MergePolicy.STRICT:
        # Richiede almeno 1 URI in comune
        if not master_uris or not candidate_uris:
            return False, "empty_uris_strict_mode"
        
        if master_uris.isdisjoint(candidate_uris):
            return False, "disjoint_uris"
        
        return True, "shared_uri_match"
    
    elif config.merge_policy == MergePolicy.LENIENT:
        # Comportamento originale
        if not master_uris or not candidate_uris or not master_uris.isdisjoint(candidate_uris):
            return True, "lenient_policy"
        else:
            return False, "disjoint_uris_lenient"
    
    elif config.merge_policy == MergePolicy.EMPTY_ONLY:
        # Merge solo se almeno uno ha URI vuote
        if not master_uris or not candidate_uris:
            return True, "empty_uris_allowed"
        else:
            return False, "both_have_uris"
    
    # Default: non mergiare
    return False, "unknown_policy"


# =============================================================================
# MAIN CLEANING FUNCTION
# =============================================================================

def clean_vault_advanced(
    input_file: str,
    output_file: Optional[str] = None,
    deleted_file: Optional[str] = None,
    log_file: Optional[str] = None,
    decision_log_file: Optional[str] = None,
    config: Optional[CleanerConfig] = None,
    log_cb: Optional[Callable[[str], None]] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> CleanerStats:
    """
    Funzione principale di pulizia avanzata.
    
    Args:
        input_file: Path del file JSON di input
        output_file: Path del file di output (opzionale)
        deleted_file: Path del file elementi eliminati (opzionale)
        log_file: Path del file di log (opzionale)
        decision_log_file: Path del decision log JSON (opzionale)
        config: Configurazione (opzionale, usa default se None)
        log_cb: Callback per logging (opzionale)
        progress_cb: Callback per progresso (opzionale)
    
    Returns:
        CleanerStats con statistiche dettagliate
    """
    start_time = datetime.datetime.now()
    
    # Setup configurazione
    if config is None:
        config = CleanerConfig()
    
    # Setup paths
    date_suffix = datetime.datetime.now().strftime("%Y%m%d")
    if output_file is None:
        output_file = f"bitwarden_cleaned_{date_suffix}.json"
    if deleted_file is None:
        deleted_file = f"bitwarden_deleted_{date_suffix}.json"
    if log_file is None:
        log_file = f"merge_log_{date_suffix}.txt"
    if decision_log_file is None and config.enable_explain:
        decision_log_file = f"merge_decisions_{date_suffix}.json"
    
    # Setup stats e decision log
    stats = CleanerStats(
        output_file=output_file,
        deleted_file=deleted_file,
        log_file=log_file,
        decision_log_file=decision_log_file or "",
    )
    
    decision_log = DecisionLog() if config.enable_explain else None
    
    # Logger interno
    def _log(msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(line + "\n")
        if log_cb:
            log_cb(line)
    
    _log("=== Bitwarden/Vaultwarden Cleaner (ADVANCED) ===")
    _log(f"Normalization level: {config.normalization_level.value}")
    _log(f"Merge policy: {config.merge_policy.value}")
    _log(f"Dry run: {config.enable_dry_run}")
    
    # Backup
    if not config.enable_dry_run:
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"File di input '{input_file}' non trovato.")
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{input_file}.{timestamp}.bak"
        shutil.copy2(input_file, backup_name)
        _log(f"Backup di sicurezza creato: {backup_name}")
    
    # Carica JSON
    with open(input_file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Il file non è un JSON valido: {e}")
    
    items = data.get("items", [])
    stats.total_start = len(items)
    _log(f"Caricati {stats.total_start} elementi.")
    
    if progress_cb:
        progress_cb(0, stats.total_start)
    
    # Raggruppamento O(N)
    grouped_logins: Dict[Tuple[str, str], List[dict]] = {}
    kept_items: List[dict] = []
    deleted_items_list: List[dict] = []
    
    for idx, item in enumerate(items, start=1):
        # Non-login items → keep as-is
        if item.get("type") != 1:
            kept_items.append(item)
            continue
        
        # Genera chiave di raggruppamento
        key = generate_grouping_key(item, config.normalization_level)
        if key is None:
            # Login senza username/password → keep
            kept_items.append(item)
            continue
        
        grouped_logins.setdefault(key, []).append(item)
        
        if progress_cb and idx % 200 == 0:
            progress_cb(idx, stats.total_start)
    
    stats.groups_analyzed = len(grouped_logins)
    _log(f"Gruppi identificati: {stats.groups_analyzed}")
    
    # Deduplicazione per gruppo
    for (username, password), group in grouped_logins.items():
        if len(group) == 1:
            # Singolo item → keep
            kept_items.append(group[0])
            stats.groups_kept_separate += 1
            continue
        
        # Sort deterministico
        group.sort(key=stable_sort_key, reverse=True)
        master = group[0]
        
        group_had_merge = False
        
        for i in range(1, len(group)):
            candidate = group[i]
            
            # Decidi se mergiare
            should_merge, reason = should_merge_items(master, candidate, config)
            
            if should_merge:
                # MERGE
                shared_uris_list = list(
                    extract_uris_normalized(master, config.normalization_level) &
                    extract_uris_normalized(candidate, config.normalization_level)
                )
                
                master, merged_fields = merge_items_advanced(master, candidate, config, decision_log)
                
                # Tracking
                if "totp" in merged_fields:
                    stats.totp_preserved += 1
                if "notes" in merged_fields:
                    stats.notes_concatenated += 1
                
                candidate["reasonForDeletion"] = f"Merged into '{master.get('name')}' (Id: {master.get('id')})"
                deleted_items_list.append(candidate)
                stats.merges_count += 1
                group_had_merge = True
                
                # Decision log
                if decision_log:
                    decision_log.add_merge(
                        master, candidate, reason,
                        shared_uris_list, merged_fields
                    )
            else:
                # KEEP SEPARATE
                kept_items.append(candidate)
                stats.uri_collisions_avoided += 1
                
                # Decision log
                if decision_log:
                    decision_log.add_kept_separate(master, candidate, reason)
        
        # Aggiungi master
        kept_items.append(master)
        
        if group_had_merge:
            stats.groups_merged += 1
            _log(f"Gruppo mergiato: username='{username[:20]}...', master='{master.get('name')}'")
        else:
            stats.groups_kept_separate += 1
    
    stats.total_end = len(kept_items)
    stats.removed = len(deleted_items_list)
    
    # Salvataggio
    if not config.enable_dry_run:
        data["items"] = kept_items
        
        # Output file
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Set permissions 0600
        os.chmod(output_file, 0o600)
        
        # Deleted file
        with open(deleted_file, "w", encoding="utf-8") as f:
            json.dump(deleted_items_list, f, indent=2, ensure_ascii=False)
        
        os.chmod(deleted_file, 0o600)
        
        # Decision log
        if decision_log and decision_log_file:
            decision_log.save(decision_log_file)
            os.chmod(decision_log_file, 0o600)
        
        _log(f"File salvati: {output_file}, {deleted_file}")
        if decision_log_file:
            _log(f"Decision log: {decision_log_file}")
    else:
        _log("[DRY RUN] Nessun file scritto.")
    
    # Calcola tempo
    end_time = datetime.datetime.now()
    stats.processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
    
    _log("=== Operazione Completata ===")
    _log(stats.summary_text())
    
    if progress_cb:
        progress_cb(stats.total_start, stats.total_start)
    
    return stats


# =============================================================================
# BACKWARD COMPATIBILITY WRAPPER
# =============================================================================

def clean_vault(
    input_file: str,
    output_file: Optional[str] = None,
    deleted_file: Optional[str] = None,
    log_file: Optional[str] = None,
    log_cb: Optional[Callable[[str], None]] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    """
    Wrapper per compatibilità con versione originale.
    
    Usa configurazione di default (comportamento conservativo).
    """
    config = CleanerConfig()  # Default settings
    
    stats = clean_vault_advanced(
        input_file=input_file,
        output_file=output_file,
        deleted_file=deleted_file,
        log_file=log_file,
        config=config,
        log_cb=log_cb,
        progress_cb=progress_cb,
    )
    
    # Ritorna dizionario per compatibilità
    return stats.to_dict()


# Default exports per compatibilità
DATE_SUFFIX = datetime.datetime.now().strftime("%Y%m%d")
DEFAULT_INPUT = "bitwarden_export_file.json"
DEFAULT_OUTPUT = f"bitwarden_cleaned_{DATE_SUFFIX}.json"
DEFAULT_DELETED = f"bitwarden_deleted_{DATE_SUFFIX}.json"
