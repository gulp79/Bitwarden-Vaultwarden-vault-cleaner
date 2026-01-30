# Bitwarden/Vaultwarden Vault Cleaner - Advanced Edition

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Deduplica conservativa e idempotente per vault Bitwarden/Vaultwarden con configurazione avanzata.**

## 🎯 Caratteristiche Principali

### ✅ Versione 2.0 (Advanced Edition)

- **Determinismo garantito**: Risultati identici indipendentemente dall'ordine di input
- **Idempotenza verificata**: `Dedup(Dedup(X)) = Dedup(X)` sempre
- **Normalizzazione parametrica**: 4 livelli (none/min/std/aggressive) con default conservativo
- **Politiche di merge configurabili**: strict/lenient/empty_only
- **Explainability**: Decision log JSON con motivazione per ogni merge
- **Dry-run mode**: Anteprima senza modifiche
- **Metriche estese**: Statistiche dettagliate su merge, URI collisions, TOTP, note
- **Test completi**: 50+ unit tests + property-based tests + integration tests
- **Performance O(N)**: Complessità lineare verificata con benchmark

### 🔒 Garanzie di Sicurezza

- **Zero perdita di informazione**: URI, note e TOTP sempre preservati
- **Backup automatico**: Copia timestampata prima di ogni operazione
- **File permissions 0600**: Output protetti automaticamente
- **Password redaction**: Credenziali mai stampate nei log
- **Comportamento conservativo di default**: Nessun rischio di falsi merge

---

## 📦 Installazione

### Requisiti

```bash
Python 3.8+
```

### Installazione dipendenze

```bash
# Base (CLI + core)
pip install -r requirements.txt

# GUI (opzionale)
pip install PySide6

# Testing (opzionale)
pip install pytest hypothesis

# Benchmark plotting (opzionale)
pip install matplotlib
```

### File del progetto

```
vw_cleaner_core_v2.py       # Core engine avanzato
vw_normalization.py          # Modulo di normalizzazione
vw_cleaner_cli_v2.py         # CLI con flag avanzati
vw_cleaner_gui.py            # GUI (compatibile con v2)
test_vw_cleaner.py           # Suite di test completa
benchmark_vw_cleaner.py      # Performance benchmark
```

---

## 🚀 Quick Start

### Uso Base (Conservativo)

```bash
# Comportamento identico alla versione originale
python vw_cleaner_cli_v2.py bitwarden_export.json

# O modalità interattiva
python vw_cleaner_cli_v2.py
```

**Criterio di merge (default):**
- Username identico
- Password identica
- **Almeno 1 URI in comune** OPPURE almeno uno dei due item senza URI

### Uso Avanzato

```bash
# STRICT mode (raccomandato per sicurezza massima)
# Merge SOLO se hanno almeno 1 URI condivisa
python vw_cleaner_cli_v2.py input.json --merge-policy=strict

# Dry run (anteprima senza scrivere)
python vw_cleaner_cli_v2.py input.json --dry-run --summary

# Explain mode (genera decision log)
python vw_cleaner_cli_v2.py input.json --explain

# Normalizzazione standard (case-insensitive username)
python vw_cleaner_cli_v2.py input.json --normalize=std

# Combinazione completa
python vw_cleaner_cli_v2.py input.json \
    --merge-policy=strict \
    --normalize=std \
    --explain \
    --summary \
    --output=cleaned.json
```

---

## 📋 Documentazione Completa

### Livelli di Normalizzazione

| Livello | Username | Password | URI | Raccomandato |
|---------|----------|----------|-----|--------------|
| **none** | Match esatto | Match esatto | Match esatto | Solo per debug |
| **min** (default) | Trim whitespace | Trim whitespace | Lowercase hostname, trim trailing `/` | ✅ **SÌ** - Conservativo |
| **std** | + case-insensitive | Trim | + default port removal, query sorting | ⚠️ Con cautela |
| **aggressive** | + rimozione special chars | Trim | + eTLD+1 reduction | ❌ **NO** - Falsi positivi! |

### Politiche di Merge

| Politica | Comportamento | Quando Usare |
|----------|---------------|--------------|
| **lenient** (default) | Merge se URI condivise O almeno uno senza URI | Compatibilità con versione originale |
| **strict** | Merge SOLO se almeno 1 URI condivisa | ✅ Massima sicurezza (raccomandato) |
| **empty_only** | Merge SOLO se almeno uno ha URI vuote | Casi speciali |

### Regole di Merge

| Campo | Strategia | Note |
|-------|-----------|------|
| **URIs** | Unione insiemistica (set union) | Tutte le URI preservate, nessuna perdita |
| **Notes** | Concatenazione con separatore | Solo se diverse; separator configurabile |
| **TOTP** | Preservazione conservativa | Copia se master vuoto; mai sovrascrive |
| **Metadati** | Opzionale (--preserve-metadata) | favorite, folderId, ecc. |

### Selezione Master

**Criterio deterministico (stable sort):**
1. `revisionDate` più recente
2. `creationDate` più recente (tie-break)
3. `id` lessicografico (ultimo tie-break)

---

## 🧪 Testing

### Esegui Test Suite

```bash
# Tutti i test
pytest test_vw_cleaner.py -v

# Solo unit tests
pytest test_vw_cleaner.py -v -k "Test"

# Con statistiche Hypothesis
pytest test_vw_cleaner.py -v --hypothesis-show-statistics

# Coverage
pytest test_vw_cleaner.py --cov=vw_cleaner_core_v2 --cov-report=html
```

### Test Inclusi

- **50+ unit tests**: Normalizzazione, grouping, merge logic, sorting
- **Property-based tests**: Idempotenza, no-loss, monotonicity
- **Integration tests**: End-to-end con dataset sintetici
- **Edge cases**: Vault vuoti, non-login items, URI disgiunte

---

## 📊 Benchmark

### Esegui Benchmark

```bash
python benchmark_vw_cleaner.py
```

**Output:**
- Tabella tempo vs N items
- Analisi complessità (regressione lineare)
- Grafico PNG (se matplotlib disponibile)
- Coefficiente R² per verificare linearità

**Risultati attesi:**
- R² > 0.95 (linearità forte)
- ~10,000 items/sec su hardware moderno
- Complessità O(N) nel caso medio

---

## 📖 Esempi Pratici

### Esempio 1: Deduplica Conservativa (Default)

```bash
python vw_cleaner_cli_v2.py my_vault.json
```

**Cosa fa:**
- Raggruppa per `(username, password)` identici
- Verifica che abbiano **almeno 1 URI in comune** OPPURE uno senza URI
- Merge: unisce URI, concatena note, preserva TOTP
- Output: `bitwarden_cleaned_YYYYMMDD.json`

### Esempio 2: Strict Mode (Massima Sicurezza)

```bash
python vw_cleaner_cli_v2.py my_vault.json --merge-policy=strict
```

**Differenza:**
- **NON** merge se URI completamente disgiunte
- Esempio: `admin/pass123` su `bank.com` e `shop.com` → **mantiene separati**
- Previene falsi positivi su credenziali riutilizzate

### Esempio 3: Dry Run + Explain

```bash
python vw_cleaner_cli_v2.py my_vault.json --dry-run --explain --summary
```

**Output:**
- File: `merge_decisions_YYYYMMDD.json` (decision log)
- Console: Summary con metriche dettagliate
- **Nessun file modificato** (solo anteprima)

**Decision Log Example:**
```json
{
  "timestamp": "2026-01-29T10:30:00Z",
  "master_id": "abc-123",
  "slave_id": "def-456",
  "decision": "merged",
  "reason": "shared_uri_match",
  "shared_uris": ["https://example.com"],
  "merged_fields": ["uris", "notes"]
}
```

### Esempio 4: Normalizzazione Standard

```bash
python vw_cleaner_cli_v2.py my_vault.json --normalize=std
```

**Effetti:**
- Username: `Admin` = `admin` (case-insensitive)
- URI: `http://example.com:80` = `http://example.com` (default port)
- Query string: `?b=2&a=1` = `?a=1&b=2` (ordinata)

---

## 🔍 Metriche Dettagliate

**Summary Output:**
```
============================================================
VAULT CLEANER - SUMMARY
============================================================
Total items (start):        1000
Total items (end):          850
Items removed:              150

Groups analyzed:            250
Groups merged:              75
Groups kept separate:       175

Merge operations:           150
URI collisions avoided:     25
TOTP seeds preserved:       10
Notes concatenated:         40

Processing time:            450 ms
============================================================
```

**Interpretazione:**
- **URI collisions avoided**: Coppie con URI disgiunte NON mergiate (in strict mode)
- **Groups kept separate**: Gruppi senza duplicati o con URI incompatibili
- **TOTP preserved**: Seed TOTP copiati da slave a master

---

## ⚙️ Configurazione Avanzata

### Via CLI

```bash
python vw_cleaner_cli_v2.py input.json \
    --normalize=std \
    --merge-policy=strict \
    --notes-separator=" | MERGED | " \
    --preserve-metadata \
    --explain \
    --summary
```

### Via Codice Python

```python
from vw_cleaner_core_v2 import clean_vault_advanced, CleanerConfig, MergePolicy
from vw_normalization import NormalizationLevel

config = CleanerConfig(
    normalization_level=NormalizationLevel.STD,
    merge_policy=MergePolicy.STRICT,
    enable_explain=True,
    enable_dry_run=False,
    preserve_all_metadata=True,
    notes_separator="\n---\n",
)

stats = clean_vault_advanced(
    input_file="input.json",
    output_file="output.json",
    config=config,
    log_cb=print,
)

print(stats.summary_text())
```

---

## 🛡️ Best Practices

### Prima di Eseguire

1. ✅ **Lavora SEMPRE su una copia** del vault export
2. ✅ **Esegui backup manuale** del vault in Bitwarden/Vaultwarden
3. ✅ **Usa --dry-run** la prima volta per verificare
4. ✅ **Leggi il decision log** (--explain) se hai dubbi

### Dopo l'Esecuzione

1. ✅ **Verifica il file cleaned** prima di importare
2. ✅ **Controlla il file deleted** per confermare merge corretti
3. ✅ **Elimina il file deleted** dopo verifica (contiene credenziali!)
4. ✅ **Testa il login** su servizi critici dopo import

### Quando Usare Strict Mode

✅ **Raccomandato:**
- Vault con credenziali riutilizzate su servizi diversi
- Priorità massima: zero falsi merge
- First-time use su vault di produzione

❌ **Non necessario:**
- Vault pulito con pochi duplicati
- Item senza URI esplicite (generici)

---

## 🐛 Troubleshooting

### "Troppi item rimossi"

**Causa:** Politica di merge troppo permissiva  
**Soluzione:**
```bash
# Usa strict mode
python vw_cleaner_cli_v2.py input.json --merge-policy=strict --dry-run
```

### "Duplicati non rilevati"

**Causa:** Normalizzazione insufficiente  
**Soluzione:**
```bash
# Aumenta livello di normalizzazione
python vw_cleaner_cli_v2.py input.json --normalize=std
```

### "File deleted contiene password"

**Normale:** Export Bitwarden contiene sempre password in chiaro  
**Soluzione:** Elimina il file dopo aver verificato il risultato

---

## 📚 Riferimenti Tecnici

### Complessità Algoritmica

**Raggruppamento:** O(N)  
- Hash map con chiave `(username, password)`

**Deduplica per gruppo:** O(G·K²) dove K = dimensione media gruppo  
- Nel caso tipico: K ≤ 5 → O(N)
- Nel caso peggiore: K = N → O(N²) (raro, vault malformato)

**Totale:** O(N) nel caso medio

### Proprietà Formali

**Idempotenza:**
```
∀ vault V: Dedup(Dedup(V)) = Dedup(V)
```

**No-Loss:**
```
∀ item i ∈ V: ∀ uri ∈ URIs(i) → uri ∈ URIs(Dedup(V))
```

**Determinismo:**
```
∀ V, V': Items(V) = Items(V') → Dedup(V) = Dedup(V')
```

---

## 🤝 Contributing

Contributi benvenuti! Per favore:

1. Fork il repository
2. Crea un branch per la feature (`git checkout -b feature/amazing`)
3. Esegui i test (`pytest test_vw_cleaner.py -v`)
4. Commit (`git commit -am 'Add amazing feature'`)
5. Push (`git push origin feature/amazing`)
6. Apri una Pull Request

---

## 📄 License

MIT License - vedi [LICENSE](LICENSE)

---

## 🙏 Credits

**Advanced Edition (v2.0):** Principal Engineer Review (2026)  
**Original Version:** [gulp79](https://github.com/gulp79)

---

## 📞 Support

- 🐛 Issues: [GitHub Issues](https://github.com/gulp79/Bitwarden-Vaultwarden-vault-cleaner/issues)
- 📧 Email: [maintainer contact]
- 💬 Discussions: [GitHub Discussions](https://github.com/gulp79/Bitwarden-Vaultwarden-vault-cleaner/discussions)

---

**⚠️ DISCLAIMER:**

Questo tool modifica i tuoi dati Bitwarden/Vaultwarden. Anche se include backup automatici e test estensivi, **l'utente è responsabile** per la sicurezza dei propri dati. Usa sempre copie del vault export e verifica i risultati prima dell'import finale.

**Nessuna garanzia espressa o implicita. Usa a tuo rischio.**

---

Made with ❤️ for the Bitwarden/Vaultwarden community
