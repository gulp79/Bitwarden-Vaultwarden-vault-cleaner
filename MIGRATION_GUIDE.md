# Guida di Migrazione - da v1.0 a v2.0 Advanced

**Data:** 2026-01-29  
**Target:** Utenti della versione originale che vogliono migrare alla Advanced Edition

---

## 📋 Indice

1. [Compatibilità Backward](#compatibilità-backward)
2. [Differenze Principali](#differenze-principali)
3. [Migration Path](#migration-path)
4. [Breaking Changes](#breaking-changes)
5. [Checklist di Migrazione](#checklist-di-migrazione)

---

## ✅ Compatibilità Backward

### La v2.0 è **100% compatibile** con la v1.0 quando usata senza flag opzionali

```bash
# v1.0 (originale)
python vw_cleaner.py

# v2.0 (comportamento identico)
python vw_cleaner_cli_v2.py
```

**Garanzie:**
- ✅ Stesso criterio di merge (default lenient)
- ✅ Stessa normalizzazione URI (min)
- ✅ Stesso output JSON
- ✅ Stessa modalità interattiva
- ✅ Stesso formato file deleted

---

## 🔄 Differenze Principali

### Miglioramenti Automatici (senza config)

| Aspetto | v1.0 | v2.0 |
|---------|------|------|
| **Determinismo** | ⚠️ Dipendente da ordine input | ✅ Sempre deterministico |
| **Idempotenza** | ✅ Teorica | ✅ Verificata con test |
| **File permissions** | ⚠️ Default OS | ✅ 0600 automatico |
| **Password nei log** | ⚠️ Possibile | ✅ Mai stampate |
| **Backup naming** | ⚠️ Timestamp secondi | ✅ Timestamp microsecondi |

### Nuove Funzionalità (opt-in)

| Funzionalità | CLI Flag | Benefit |
|--------------|----------|---------|
| Strict mode | `--merge-policy=strict` | Zero falsi merge |
| Dry run | `--dry-run` | Anteprima sicura |
| Decision log | `--explain` | Auditability completa |
| Summary esteso | `--summary` | Metriche dettagliate |
| Normalizzazione avanzata | `--normalize=std` | Più duplicati trovati |

---

## 🛤️ Migration Path

### Scenario 1: "Voglio solo i fix, nessun cambiamento"

**Azione:** Nessuna. Usa la v2.0 esattamente come la v1.0

```bash
# Drop-in replacement
python vw_cleaner_cli_v2.py input.json
```

**Benefici automatici:**
- Determinismo garantito
- File permissions 0600
- Password redaction nei log

### Scenario 2: "Voglio maggior sicurezza"

**Azione:** Abilita strict mode

```bash
python vw_cleaner_cli_v2.py input.json --merge-policy=strict
```

**Cosa cambia:**
- ⚠️ Meno merge (più sicuro, ma duplicati con URI disgiunte NON vengono uniti)
- ✅ Zero falsi positivi su credenziali riutilizzate

**Quando usare:**
- Vault con admin/admin su servizi diversi
- Priorità massima: nessun errore

### Scenario 3: "Voglio trovare più duplicati"

**Azione:** Usa normalizzazione std

```bash
python vw_cleaner_cli_v2.py input.json --normalize=std
```

**Cosa cambia:**
- Username: case-insensitive (Admin = admin)
- URI: default port removal, query sorting
- ⚠️ Leggermente più aggressivo, ma ancora sicuro

**Quando usare:**
- Vault con inconsistenze di case
- Duplicati non rilevati in v1.0

### Scenario 4: "Voglio full control"

**Azione:** Usa tutti i flag

```bash
python vw_cleaner_cli_v2.py input.json \
    --merge-policy=strict \
    --normalize=std \
    --dry-run \
    --explain \
    --summary
```

**Workflow:**
1. Dry run → verifica cosa succederebbe
2. Leggi decision log → capisce perché
3. Conferma → rimuovi --dry-run
4. Verifica summary → valida risultati

---

## ⚠️ Breaking Changes

### Nessuno per Utenti Standard

Se usi:
```bash
python vw_cleaner.py
```

La v2.0 ha **zero breaking changes**.

### Breaking per Utenti Avanzati (se importi come modulo Python)

#### 1. Import Path Cambiato

```python
# v1.0
from vw_cleaner_core import clean_vault

# v2.0 (backward compatible wrapper)
from vw_cleaner_core_v2 import clean_vault  # Stesso signature

# v2.0 (new API)
from vw_cleaner_core_v2 import clean_vault_advanced, CleanerConfig
```

#### 2. Return Type Arricchito

```python
# v1.0
stats = clean_vault(...)
# stats = dict con: total_start, total_end, removed, merges

# v2.0 (backward compatible)
stats = clean_vault(...)
# stats = dict (stesso formato + campi extra)

# v2.0 (new API)
stats = clean_vault_advanced(...)
# stats = CleanerStats object con .to_dict()
```

#### 3. Normalizzazione Opzionale

```python
# v1.0
def normalize_uri(uri): ...

# v2.0
from vw_normalization import normalize_uri_min  # Equivalente
from vw_normalization import normalize_uri_std  # Nuovo
```

---

## 📝 Checklist di Migrazione

### Pre-Migration

- [ ] Backup completo del vault in Bitwarden/Vaultwarden
- [ ] Export vault come JSON
- [ ] Copia l'export in directory di lavoro
- [ ] Installa dipendenze: `pip install -r requirements.txt`
- [ ] (Opzionale) Installa test: `pip install pytest hypothesis`

### Testing della v2.0

- [ ] Test con dry-run: `python vw_cleaner_cli_v2.py input.json --dry-run --summary`
- [ ] Verifica metriche nel summary (plausibili?)
- [ ] (Opzionale) Genera decision log: `--explain`
- [ ] Leggi decision log per capire merge
- [ ] Confronta con v1.0 se hai dubbi

### Migration Effettiva

- [ ] Rimuovi --dry-run e esegui realmente
- [ ] Verifica file output (`bitwarden_cleaned_*.json`)
- [ ] Verifica file deleted (`bitwarden_deleted_*.json`)
- [ ] Controlla che item critici non siano stati mergiati erroneamente
- [ ] (Opzionale) Test import in Bitwarden/Vaultwarden su account test

### Post-Migration

- [ ] Import in Bitwarden/Vaultwarden
- [ ] Test login su servizi critici
- [ ] Elimina file deleted (contiene password!)
- [ ] Archivia backup originale
- [ ] (Opzionale) Esegui test idempotenza: stesso risultato su secondo run?

### Troubleshooting

Se qualcosa non va:

1. **Non panic:** Hai il backup
2. **Confronta:** v1.0 vs v2.0 con --dry-run
3. **Usa strict:** Se troppi merge, prova `--merge-policy=strict`
4. **Riduci normalizzazione:** Se falsi positivi, usa `--normalize=none`
5. **Leggi decision log:** Capisci cosa è stato mergiato e perché

---

## 🎓 Tutorial: Prima Migrazione Step-by-Step

### Step 1: Setup

```bash
# Crea directory di lavoro
mkdir vault_migration
cd vault_migration

# Copia export
cp ~/Downloads/bitwarden_export.json input.json

# Backup manuale
cp input.json input_backup.json
```

### Step 2: Test v2.0 (Dry Run)

```bash
python vw_cleaner_cli_v2.py input.json --dry-run --summary --explain
```

**Output atteso:**
```
=== Bitwarden/Vaultwarden Vault Cleaner (Advanced) ===
Input:          input.json
Normalization:  min
Merge policy:   lenient
Dry run:        YES
Explain:        YES

[... processing ...]

============================================================
VAULT CLEANER - SUMMARY
============================================================
Total items (start):        500
Total items (end):          450
Items removed:              50

Groups analyzed:            120
Groups merged:              30
Groups kept separate:       90

Merge operations:           50
URI collisions avoided:     5
TOTP seeds preserved:       2
Notes concatenated:         10

Processing time:            120 ms

Output files:
  - Cleaned:  bitwarden_cleaned_20260129.json
  - Deleted:  bitwarden_deleted_20260129.json
  - Log:      merge_log_20260129.txt
  - Decisions: merge_decisions_20260129.json
============================================================

ℹ️  Dry run completato - nessun file modificato
   Rimuovi --dry-run per applicare le modifiche
```

### Step 3: Analizza Decision Log

```bash
cat merge_decisions_*.json | jq '.[0:5]'  # Mostra primi 5 merge
```

**Verifica:**
- Merge hanno senso?
- URI condivise sono corrette?
- Note mergiate come previsto?

### Step 4: Esegui Realmente

```bash
# Rimuovi --dry-run
python vw_cleaner_cli_v2.py input.json --summary --explain
```

### Step 5: Verifica Output

```bash
# Confronta dimensioni
ls -lh input.json bitwarden_cleaned_*.json

# Conta item
jq '.items | length' input.json
jq '.items | length' bitwarden_cleaned_*.json

# Verifica deleted
jq '.items | length' bitwarden_deleted_*.json
```

### Step 6: Test Idempotenza

```bash
# Esegui di nuovo sullo stesso output
python vw_cleaner_cli_v2.py bitwarden_cleaned_20260129.json \
    -o cleaned_second_pass.json \
    --summary

# Verifica: removed dovrebbe essere 0
```

**Output atteso:**
```
Items removed:              0
```

✅ Se 0 → idempotenza confermata!

### Step 7: Import in Bitwarden

1. Login in Bitwarden/Vaultwarden
2. Tools → Import Data
3. Scegli "Bitwarden (json)"
4. Carica `bitwarden_cleaned_*.json`
5. Verifica import riuscito

### Step 8: Cleanup

```bash
# Elimina file con password
rm bitwarden_deleted_*.json

# Archivia backup
mkdir archive
mv input_backup.json archive/
mv *.bak archive/
```

---

## 🔬 Confronto v1.0 vs v2.0

### Test Comparativo

```bash
# v1.0
python vw_cleaner.py input.json
mv bitwarden_cleaned_*.json output_v1.json

# v2.0 (default settings)
python vw_cleaner_cli_v2.py input.json
mv bitwarden_cleaned_*.json output_v2.json

# Confronta
diff <(jq -S '.items | sort_by(.id)' output_v1.json) \
     <(jq -S '.items | sort_by(.id)' output_v2.json)
```

**Risultato atteso:** Differenze minime o nulle (solo ordinamento interno)

---

## 📊 Metriche di Migrazione

### Success Criteria

✅ **Migration riuscita se:**
- Idempotenza verificata (secondo run non rimuove nulla)
- Numero di item finali ragionevole (non troppo pochi/molti)
- Decision log ha senso
- Import in Bitwarden/Vaultwarden funziona
- Login su servizi critici funziona

⚠️ **Rollback se:**
- Troppi item rimossi (>30% del totale)
- Merge evidentemente sbagliati
- Import fallisce

### Metriche Tipiche

| Metrica | Valore Tipico | Red Flag |
|---------|---------------|----------|
| % Removed | 10-30% | >50% |
| Groups merged | 20-40% dei gruppi | >80% |
| URI collisions avoided | 5-15% (strict mode) | N/A |
| Processing time | <1s per 1000 item | >10s |

---

## 🆘 Supporto

**Problemi durante migrazione?**

1. 📖 Leggi questa guida completamente
2. 🧪 Esegui test suite: `pytest test_vw_cleaner.py -v`
3. 🐛 Apri issue su GitHub con:
   - Comando eseguito
   - Summary output
   - Decision log (senza password!)
   - Comportamento atteso vs ottenuto

---

## ✅ Conclusione

La migrazione da v1.0 a v2.0 è:
- **Sicura**: Backward compatible al 100%
- **Opzionale**: Benefici anche senza config
- **Graduale**: Puoi abilitare feature una alla volta
- **Reversibile**: Backup automatici sempre presenti

**Raccomandazione:** Inizia con dry-run, poi usa default settings, infine abilita strict mode se necessario.

---

Happy migration! 🚀
