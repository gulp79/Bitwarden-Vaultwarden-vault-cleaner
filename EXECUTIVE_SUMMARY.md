# Executive Summary - Revisione Bitwarden/Vaultwarden Vault Cleaner

**Data:** 2026-01-29  
**Revisore:** Principal Engineer Review  
**Repository:** https://github.com/gulp79/Bitwarden-Vaultwarden-vault-cleaner

---

## 1. ANALISI DELLO STATO ATTUALE

### 1.1 Formalizzazione della Relazione di Equivalenza

L'algoritmo attuale implementa la seguente **relazione di equivalenza** tra due entry `e₁` e `e₂`:

```
Equivalent(e₁, e₂) ↔ 
    ∧ Type(e₁) = Type(e₂) = LOGIN (type=1)
    ∧ Username(e₁) = Username(e₂)  [case-sensitive, exact match]
    ∧ Password(e₁) = Password(e₂)  [case-sensitive, exact match]
    ∧ CanMerge(URIs(e₁), URIs(e₂))

dove:
    CanMerge(U₁, U₂) ↔ 
        U₁ = ∅ ∨ U₂ = ∅ ∨ ∃u ∈ U₁, v ∈ U₂: Normalize(u) = Normalize(v)
```

**Normalizzazione URI** (righe 12-15):
```
Normalize(uri) = strip(lowercase(rstrip(uri, '/')))
```

### 1.2 Strategia di Raggruppamento e Complessità

**Complessità Temporale:** O(N) per il raggruppamento + O(G·K²) per la deduplica  
dove:
- N = numero totale di item
- G = numero di gruppi con stesse credenziali
- K = dimensione media di un gruppo

**Implementazione:**
1. Prima passata (righe 98-114): raggruppa per chiave `(username, password)` → O(N)
2. Seconda passata (righe 119-165): per ogni gruppo, confronta N-wise gli item → O(G·K²)

**Nel caso peggiore** (tutti gli item con stesse credenziali ma URI diverse): O(N²)  
**Nel caso medio** (K piccolo, tipicamente ≤ 5): O(N)

### 1.3 Regole di Merge (funzione `merge_items`, righe 27-49)

| Campo | Strategia | Note |
|-------|-----------|------|
| **URIs** | Unione insiemistica con dedup basata su `normalize_uri()` | Mantiene oggetti URI originali, aggiunge solo se non presenti |
| **Notes** | Concatenazione con separatore fisso `"\n\n--- MERGED NOTES ---\n"` | Solo se diverse; se master vuoto → copia diretta |
| **TOTP** | Preservazione conservativa | Copia solo se master vuoto; NON sovrascrive se entrambi presenti |
| **Altri campi** | Nessun merge esplicito | Password, username, type, id, folders, favorites ecc. → mantenuti dal master |

**Selezione Master** (riga 124):
```python
group.sort(key=lambda x: x.get("revisionDate", ""), reverse=True)
master = group[0]
```
Criterio: **revisionDate più recente** (lessicografico su stringa ISO)

---

## 2. CRITICITÀ E RISCHI IDENTIFICATI

### 2.1 FALSI POSITIVI (merge non desiderati)

#### ⚠️ CRITICO: Merge con URI completamente disgiunte
**Condizione attuale (righe 142-146):**
```python
should_merge = (
    not master_uri_set or           # Master senza URI → MERGE
    not candidate_uris or           # Candidate senza URI → MERGE
    not master_uri_set.isdisjoint(candidate_uris)  # Almeno 1 URI in comune → MERGE
)
```

**Problema:** Se uno dei due item NON ha URI, il merge avviene sempre, anche se l'altro item ha URI completamente non correlate.

**Esempio:**
- Item A: username=`admin`, password=`pass123`, URIs=`[]` (nessuna URI)
- Item B: username=`admin`, password=`pass123`, URIs=`["https://bank.com"]`
- **Risultato:** MERGE (perché `not master_uri_set = True`)

**Impatto:** Account con stesse credenziali ma per servizi diversi potrebbero essere uniti erroneamente se uno dei due non ha URI esplicite.

**Giustificazione originale:** È ragionevole presumere che item senza URI siano generici, ma potrebbe portare a perdita di contesto semantico.

#### ⚠️ MEDIO: Normalizzazione URI troppo aggressiva

**Problema attuale:**
```python
normalize_uri("HTTP://Example.COM/Path") → "http://example.com/path"
```
- `lowercase()` potrebbe alterare URI case-sensitive (non comuni ma esistenti)
- `rstrip("/")` tratta `http://a.com` e `http://a.com/` come identici (corretto in HTTP, ma path potrebbe essere semanticamente diverso in rari casi)

#### ⚠️ BASSO: Ordine non deterministico in caso di `revisionDate` identici

Se due item hanno `revisionDate` uguale, l'ordine dipende dall'ordine di input (sort non è stabile per chiavi uguali se non specificato).

### 2.2 FALSI NEGATIVI (duplicati non riconosciuti)

#### ⚠️ MEDIO: Username con whitespace o case diverse

- `"user@example.com"` vs `" user@example.com "` (spazio iniziale)
- `"Admin"` vs `"admin"` (case differente)

Non vengono riconosciuti come duplicati, anche se potrebbero esserlo.

#### ⚠️ BASSO: Password con encoding diverso o artefatti

Molto raro, ma possibile se export/import ha avuto problemi di encoding.

### 2.3 PROBLEMI DI IDEMPOTENZA E DETERMINISMO

#### ✅ IDEMPOTENZA: Verificata teoricamente

Se si esegue `Dedup(Dedup(X))`:
- Seconda esecuzione: non ci saranno più gruppi con >1 item (tutti già mergiati)
- Output invariato ✅

#### ⚠️ DETERMINISMO: Non garantito in tutti i casi

**Problema 1:** `revisionDate` uguale → ordine dipendente da input
**Problema 2:** Iterazione su `dict.items()` (riga 119) mantiene ordine di inserimento in Python 3.7+, ma logica di merge potrebbe comunque variare se ci sono item con URI parzialmente sovrapposte in ordine diverso.

**Esempio di non-determinismo potenziale:**
```
Input A: [item1(URIs=[a,b]), item2(URIs=[b,c]), item3(URIs=[c,d])]
Input B: [item3(URIs=[c,d]), item1(URIs=[a,b]), item2(URIs=[b,c])]
```
Se `revisionDate` uguale, master selezionato potrebbe essere diverso → URI finali diverse (tutte presenti, ma ordine diverso).

### 2.4 PERDITA DI INFORMAZIONE

#### ✅ ZERO PERDITA: URI e Note

- URI: tutte preservate (unione)
- Note: tutte concatenate
- TOTP: preservato se disponibile

#### ⚠️ PERDITA POTENZIALE: Metadati

Campi come:
- `creationDate`, `revisionDate`, `deletedDate` del slave → persi
- `folders`, `organizationId`, `collectionIds` del slave → persi
- `favorite`, `reprompt` del slave → persi
- Custom fields, attachments, passwordHistory → NON verificati nel codice

---

## 3. DECISIONI LOGICHE E MITIGAZIONI PROPOSTE

### 3.1 Strategia di Normalizzazione a Livelli

**Default: `--normalize=min` (conservativo)**
```python
normalize_username(u):
    return u.strip()  # Solo trim whitespace

normalize_uri(uri):
    return uri.strip().lower().rstrip("/")  # Come attuale

normalize_password(p):
    return p  # No normalizzazione (match esatto)
```

**Opzionale: `--normalize=std`**
```python
normalize_username(u):
    return u.strip().lower()  # + case insensitive

normalize_uri(uri):
    # + rimozione default port (80/443)
    # + query string ordering
    # + fragment removal (opzionale)
```

### 3.2 Firma di Raggruppamento O(N) Ottimizzata

**Chiave di hash:**
```python
key = (normalize_username(u), normalize_password(p))
```

**Filtro di collisione post-hash:**
- Per ogni gruppo con chiave identica
- Verifica **almeno una URI in comune** (parametro `--require-shared-uri`)
- Se `--require-shared-uri=strict`: **obbligatorio** avere ≥1 URI comune
- Se `--require-shared-uri=lenient`: **opzionale** (comportamento attuale)

### 3.3 Ordinamento Deterministico

**Proposta:**
```python
def stable_sort_key(item):
    revision = item.get("revisionDate", "")
    creation = item.get("creationDate", "")
    item_id = item.get("id", "")
    return (revision, creation, item_id)

group.sort(key=stable_sort_key, reverse=True)
```

Garantisce determinismo totale anche con `revisionDate` identici.

### 3.4 Registro Decisionale (Explainability)

Per ogni merge, registrare:
```json
{
  "decision": "merged",
  "master_id": "abc-123",
  "slave_id": "def-456",
  "reason": "shared_uri_match",
  "shared_uris": ["https://example.com"],
  "merged_fields": ["uris", "notes"],
  "timestamp": "2026-01-29T10:30:00Z"
}
```

Flag CLI: `--explain` → genera `merge_decisions_YYYYMMDD.json`

---

## 4. METRICHE DI QUALITÀ

### 4.1 Metriche Attuali (da `stats`)

| Metrica | Descrizione |
|---------|-------------|
| `total_start` | Numero di item iniziali |
| `total_end` | Numero di item finali |
| `removed` | Numero di item rimossi |
| `merges` | Numero di merge effettuati |

### 4.2 Metriche Proposte (estese)

| Metrica | Descrizione | Importanza |
|---------|-------------|------------|
| `groups_analyzed` | Numero di gruppi (username,password) | Media |
| `groups_merged` | Gruppi che hanno avuto almeno un merge | Alta |
| `uri_collisions_avoided` | Coppie con URI disgiunte NON mergiate | Alta |
| `totp_preserved` | Seed TOTP copiati da slave a master | Media |
| `notes_concatenated` | Note concatenate | Bassa |
| `processing_time_ms` | Tempo totale elaborazione | Alta |
| `memory_peak_mb` | Picco memoria (se misurabile) | Media |

---

## 5. RISCHI RESIDUI E RACCOMANDAZIONI

### 5.1 Rischi Accettabili (con flag conservativi di default)

✅ **Merge di item senza URI con item con URI:** Accettabile come comportamento di default, ma documentare chiaramente e fornire flag `--require-shared-uri=strict`.

✅ **Normalizzazione case-insensitive degli hostname:** Standard HTTP, accettabile.

✅ **Perdita metadati slave:** Accettabile se documentato (focus su credenziali/URI/note/TOTP).

### 5.2 Rischi da Mitigare

⚠️ **Non-determinismo con `revisionDate` identici:** Risolvibile con `stable_sort_key`.

⚠️ **Falsi negativi per username con whitespace:** Risolvibile con `strip()` di default.

⚠️ **Mancanza di test automatici:** CRITICO → implementare suite completa.

### 5.3 Raccomandazioni Operative

1. **SEMPRE eseguire su copia del vault**
2. **Verificare il file `deleted` prima di eliminarlo**
3. **Usare `--dry-run` la prima volta su vault di produzione**
4. **Confrontare le metriche con aspettative (es. se `removed > 50%` → sospetto)**
5. **Mantenere backup temporizzati automatici**

---

## 6. ROADMAP DI IMPLEMENTAZIONE

### Fase 1: Foundation (Priorità ALTA)
- [ ] Modulo di normalizzazione parametrico
- [ ] Stable sort con tie-break deterministico
- [ ] Logging strutturato con livelli
- [ ] Unit test base (normalizzazione, merge)

### Fase 2: Robustness (Priorità ALTA)
- [ ] Property-based tests (Hypothesis)
- [ ] Test di idempotenza automatico
- [ ] Test casi limite (URI disgiunte, TOTP conflicts, etc.)
- [ ] Benchmark performance O(N)

### Fase 3: Features (Priorità MEDIA)
- [ ] Flag CLI estesi (`--normalize`, `--require-shared-uri`, `--explain`)
- [ ] Dry-run con diff leggibile
- [ ] Report summary con metriche estese
- [ ] Registro decisionale JSON

### Fase 4: Hardening (Priorità MEDIA)
- [ ] File permissions 0600
- [ ] Redaction password nei log
- [ ] Memory profiling
- [ ] Documentazione completa

---

## 7. CONCLUSIONI

### Punti di Forza Attuali
✅ Implementazione pulita e leggibile  
✅ Complessità O(N) nel caso medio  
✅ Backup automatico  
✅ Zero perdita di URI/note/TOTP  
✅ Interfaccia GUI professionale

### Aree di Miglioramento Critiche
⚠️ **Mancanza di test automatici**  
⚠️ **Non-determinismo potenziale**  
⚠️ **Normalizzazione non parametrica**  
⚠️ **Nessun dry-run o explain mode**  
⚠️ **Metriche limitate**

### Valutazione Complessiva
**Livello di Maturità:** 3/5 (Production-Ready con limitazioni)  
**Sicurezza:** 4/5 (Backup automatico, nessuna perdita dati critici)  
**Testabilità:** 1/5 (Nessun test)  
**Usabilità:** 4/5 (GUI eccellente, CLI basica)  

**Raccomandazione:** ✅ Utilizzabile in produzione con cautela (sempre con backup e verifica manuale post-merge). Implementare urgentemente test e parametrizzazione per raggiungere livello 5/5.
