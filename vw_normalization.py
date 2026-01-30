"""
Modulo di normalizzazione per Bitwarden/Vaultwarden Vault Cleaner.

Fornisce funzioni pure e testate per normalizzare username, password, URI
con livelli progressivi di aggressività, mantenendo default conservativi.

Livelli di normalizzazione:
- none: nessuna normalizzazione (match esatto)
- min: normalizzazione minimale e sicura (default)
- std: normalizzazione standard (case-insensitive, whitespace, ecc.)
- aggressive: normalizzazione massima (eTLD+1, ecc.) - NON raccomandato

Author: Principal Engineer Review
Date: 2026-01-29
"""

import re
from typing import Optional, Tuple
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from enum import Enum


class NormalizationLevel(Enum):
    """Livelli di normalizzazione disponibili."""
    NONE = "none"
    MIN = "min"
    STD = "std"
    AGGRESSIVE = "aggressive"


# =============================================================================
# USERNAME NORMALIZATION
# =============================================================================

def normalize_username_none(username: str) -> str:
    """Nessuna normalizzazione - match esatto."""
    return username


def normalize_username_min(username: str) -> str:
    """
    Normalizzazione minimale: rimuove solo whitespace iniziale/finale.
    
    Rationale: gli utenti spesso copiano/incollano username con spazi
    accidentali, ma il contenuto effettivo deve rimanere identico.
    """
    return username.strip()


def normalize_username_std(username: str) -> str:
    """
    Normalizzazione standard: trim + lowercase.
    
    Rationale: la maggior parte dei sistemi tratta username case-insensitive.
    """
    return username.strip().lower()


def normalize_username_aggressive(username: str) -> str:
    """
    Normalizzazione aggressiva: trim + lowercase + rimozione caratteri speciali.
    
    WARNING: Può causare falsi positivi. Non raccomandato.
    """
    normalized = username.strip().lower()
    # Rimuove caratteri non alfanumerici (eccetto @ . - _)
    normalized = re.sub(r'[^\w@.\-]', '', normalized)
    return normalized


# =============================================================================
# PASSWORD NORMALIZATION
# =============================================================================

def normalize_password_none(password: str) -> str:
    """Nessuna normalizzazione - match esatto (raccomandato)."""
    return password


def normalize_password_min(password: str) -> str:
    """
    Normalizzazione minimale: rimuove SOLO whitespace iniziale/finale.
    
    Rationale: password con whitespace interne sono valide e comuni.
    Rimuovere spazi esterni previene errori di copia/incolla.
    """
    return password.strip()


# NOTE: Non implementiamo std/aggressive per password - troppo rischioso


# =============================================================================
# URI NORMALIZATION
# =============================================================================

def normalize_uri_none(uri: str) -> str:
    """Nessuna normalizzazione - match esatto."""
    return uri.strip()


def normalize_uri_min(uri: str) -> str:
    """
    Normalizzazione minimale: trim + lowercase hostname + rimozione trailing slash.
    
    Questo è il comportamento attuale dello script originale.
    Rationale: RFC 3986 - hostname è case-insensitive, trailing slash è opzionale.
    """
    if not uri:
        return ""
    return uri.strip().lower().rstrip("/")


def normalize_uri_std(uri: str) -> str:
    """
    Normalizzazione standard:
    - lowercase hostname
    - rimozione trailing slash
    - rimozione porte di default (80 per http, 443 per https)
    - rimozione fragment (#anchor)
    - ordinamento query string (opzionale)
    
    Rationale: URL equivalenti secondo RFC 3986.
    """
    if not uri:
        return ""
    
    uri = uri.strip()
    
    # Parse URL
    try:
        parsed = urlparse(uri)
    except Exception:
        # Se parsing fallisce, fallback a min
        return normalize_uri_min(uri)
    
    # Lowercase scheme e hostname
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # Rimuovi porte di default
    if ':' in netloc:
        host, port = netloc.rsplit(':', 1)
        if (scheme == 'http' and port == '80') or (scheme == 'https' and port == '443'):
            netloc = host
    
    # Rimuovi trailing slash da path (se non è root)
    path = parsed.path.rstrip('/') if parsed.path != '/' else parsed.path
    
    # Ordina query string per confronto consistente
    query = parsed.query
    if query:
        try:
            params = parse_qs(query, keep_blank_values=True)
            # Ordina per chiave
            sorted_params = sorted(params.items())
            query = urlencode(sorted_params, doseq=True)
        except Exception:
            pass  # Mantieni query originale se parsing fallisce
    
    # Rimuovi fragment (anchor)
    fragment = ""
    
    # Ricostruisci URL
    normalized = urlunparse((scheme, netloc, path, parsed.params, query, fragment))
    
    return normalized


def normalize_uri_aggressive(uri: str) -> str:
    """
    Normalizzazione aggressiva:
    - Tutto lo std
    - Riduzione a eTLD+1 (effective top-level domain + 1 label)
    - Rimozione di www.
    
    WARNING: Può causare MOLTI falsi positivi!
    Esempio: "login.example.com" e "api.example.com" → "example.com"
    NON RACCOMANDATO per vault Bitwarden.
    """
    normalized = normalize_uri_std(uri)
    
    if not normalized:
        return ""
    
    try:
        parsed = urlparse(normalized)
        netloc = parsed.netloc
        
        # Rimuovi www.
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        
        # Estrai eTLD+1 (semplificato - non usa Public Suffix List)
        parts = netloc.split('.')
        if len(parts) >= 2:
            # Prende ultimi 2 componenti (es. example.com)
            netloc = '.'.join(parts[-2:])
        
        # Mantieni solo scheme + eTLD+1
        return f"{parsed.scheme}://{netloc}"
    except Exception:
        return normalized


# =============================================================================
# URI COMPARISON HELPERS
# =============================================================================

def extract_uris_normalized(item: dict, level: NormalizationLevel = NormalizationLevel.MIN) -> set:
    """
    Estrae e normalizza tutti gli URI da un item Bitwarden.
    
    Args:
        item: Item Bitwarden (dict)
        level: Livello di normalizzazione da applicare
    
    Returns:
        Set di URI normalizzati (stringhe)
    """
    login = item.get("login", {}) or {}
    uris_list = login.get("uris", []) or []
    
    normalizer = get_uri_normalizer(level)
    
    return {
        normalizer(u.get("uri", ""))
        for u in uris_list
        if u.get("uri")
    }


def have_shared_uri(item1: dict, item2: dict, level: NormalizationLevel = NormalizationLevel.MIN) -> bool:
    """
    Verifica se due item hanno almeno un URI in comune (dopo normalizzazione).
    
    Args:
        item1, item2: Item Bitwarden da confrontare
        level: Livello di normalizzazione
    
    Returns:
        True se esiste almeno un URI comune
    """
    uris1 = extract_uris_normalized(item1, level)
    uris2 = extract_uris_normalized(item2, level)
    
    # Empty sets
    if not uris1 or not uris2:
        return False
    
    # Check intersection
    return not uris1.isdisjoint(uris2)


# =============================================================================
# NORMALIZER FACTORIES
# =============================================================================

def get_username_normalizer(level: NormalizationLevel):
    """Ritorna la funzione di normalizzazione username per il livello specificato."""
    mapping = {
        NormalizationLevel.NONE: normalize_username_none,
        NormalizationLevel.MIN: normalize_username_min,
        NormalizationLevel.STD: normalize_username_std,
        NormalizationLevel.AGGRESSIVE: normalize_username_aggressive,
    }
    return mapping[level]


def get_password_normalizer(level: NormalizationLevel):
    """Ritorna la funzione di normalizzazione password per il livello specificato."""
    if level in (NormalizationLevel.NONE, NormalizationLevel.AGGRESSIVE):
        return normalize_password_none
    else:
        # MIN e STD usano entrambi la stessa normalizzazione minima
        return normalize_password_min


def get_uri_normalizer(level: NormalizationLevel):
    """Ritorna la funzione di normalizzazione URI per il livello specificato."""
    mapping = {
        NormalizationLevel.NONE: normalize_uri_none,
        NormalizationLevel.MIN: normalize_uri_min,
        NormalizationLevel.STD: normalize_uri_std,
        NormalizationLevel.AGGRESSIVE: normalize_uri_aggressive,
    }
    return mapping[level]


# =============================================================================
# GROUPING KEY GENERATION
# =============================================================================

def generate_grouping_key(item: dict, level: NormalizationLevel = NormalizationLevel.MIN) -> Optional[Tuple[str, str]]:
    """
    Genera la chiave di raggruppamento per un item login.
    
    Args:
        item: Item Bitwarden
        level: Livello di normalizzazione
    
    Returns:
        Tupla (username_norm, password_norm) o None se non è un login valido
    """
    # Verifica tipo
    if item.get("type") != 1:  # Non è un login
        return None
    
    login = item.get("login", {}) or {}
    username = login.get("username")
    password = login.get("password")
    
    # Verifica presenza credenziali
    if not username or not password:
        return None
    
    # Normalizza
    username_normalizer = get_username_normalizer(level)
    password_normalizer = get_password_normalizer(level)
    
    username_norm = username_normalizer(username)
    password_norm = password_normalizer(password)
    
    return (username_norm, password_norm)


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def is_valid_uri(uri: str) -> bool:
    """
    Valida se una stringa è un URI valido.
    
    Controlli basici:
    - Non vuoto
    - Contiene uno scheme valido (http, https, ftp, etc.)
    - Parsing non fallisce
    """
    if not uri or not uri.strip():
        return False
    
    try:
        parsed = urlparse(uri.strip())
        # Deve avere almeno scheme e netloc
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def validate_normalization_safety(original: str, normalized: str, field_name: str) -> bool:
    """
    Verifica che la normalizzazione non abbia alterato eccessivamente il valore.
    
    Args:
        original: Valore originale
        normalized: Valore normalizzato
        field_name: Nome del campo (per logging)
    
    Returns:
        True se la normalizzazione è sicura
    """
    # Se normalizzato è vuoto ma originale no → unsafe
    if not normalized and original:
        return False
    
    # Se lunghezza cambia drasticamente → potenzialmente unsafe
    if len(normalized) < len(original) * 0.5:
        # Ha perso più del 50% dei caratteri
        return False
    
    return True


# =============================================================================
# CONSTANTS & DEFAULTS
# =============================================================================

DEFAULT_NORMALIZATION_LEVEL = NormalizationLevel.MIN

# Livelli raccomandati per uso
SAFE_LEVELS = [NormalizationLevel.NONE, NormalizationLevel.MIN]
MODERATE_LEVELS = [NormalizationLevel.STD]
RISKY_LEVELS = [NormalizationLevel.AGGRESSIVE]


if __name__ == "__main__":
    # Quick self-test
    print("=== Normalization Module Self-Test ===")
    
    test_username = " User@Example.COM "
    print(f"\nUsername: '{test_username}'")
    for level in NormalizationLevel:
        norm = get_username_normalizer(level)
        print(f"  {level.value:12} → '{norm(test_username)}'")
    
    test_uri = "HTTP://Example.com:80/Path/?query=1&other=2#fragment"
    print(f"\nURI: '{test_uri}'")
    for level in NormalizationLevel:
        norm = get_uri_normalizer(level)
        print(f"  {level.value:12} → '{norm(test_uri)}'")
    
    print("\n✅ Module loaded successfully")
