# Bitwarden/Vaultwarden Vault Cleaner (vw_cleaner.py)

A powerful, safe, and fast Python script for **deduplicating** and **cleaning** Bitwarden or Vaultwarden export JSON files.

---

## ⚠️ SECURITY WARNING: READ CAREFULLY

This script **handles your unencrypted passwords in plaintext** during processing.

1.  **Always work on a COPY of your export file.**
2.  The script automatically creates a **timestamped backup** (`.bak`) of the input file before any action.
3.  The **deleted items file** (`bitwarden_deleted_YYYYMMDD.json`) contains the full, unencrypted details of the removed login entries. **DELETE THIS FILE IMMEDIATELY** after you have verified the results and successfully imported the cleaned vault.

---

## ✨ Features

This script is an optimized implementation focused on safety, speed, and intelligent data preservation, addressing performance and safety issues found in older community scripts.

| Feature | Description | Benefit |
| :--- | :--- | :--- |
| **🚀 Optimized Performance** | Uses hash map grouping ($O(N)$ complexity) and performs the file write only **once** at the end. | **Extremely fast** on large vaults, avoiding the slow $O(N^2)$ iteration and repeated disk I/O of older scripts. |
| **🛡️ Safe Processing** | Automatically creates a timestamped backup (`.bak`) of the input file (`my_export.json.20251126_HHMMSS.bak`). | Prevents accidental data loss. |
| **🧠 Conservative Deduplication** | Items are only merged if they share the **exact same Username and Password** AND they have at least one **URI in common**. | Prevents merging accounts for different sites that merely share credentials (e.g., merging "Amazon" and "Netflix"). |
| **🔗 Smart Data Merge** | When merging, the script intelligently combines data to prevent loss: | Preserves valuable notes and credentials. |
| | - **URIs:** All unique URIs from both entries are preserved. | |
| | - **Notes:** If different, notes are concatenated with a separator (`--- MERGED NOTES ---`). | |
| | - **TOTP:** If the master item lacks a TOTP seed and the duplicate has one, the seed is preserved. | |
| **⚙️ CLI Ready (Non-Interactive)** | Supports command-line arguments for seamless batch execution. | Ideal for automation and scripting. |
| **📅 Timestamped Output** | Output and deleted files are automatically named with the current date (e.g., `bitwarden_cleaned_20251126.json`). | Easy versioning and archiving of deleted records. |

---

## 📥 Requirements

* **Python 3.6+** (Tested on all modern Python 3 versions)

---

## 🛠️ Setup and Installation

1.  **Save the script:** Save the Python code as `vw_cleaner.py`.
2.  **Export your vault:** Export your Bitwarden or Vaultwarden vault data as an **Unencrypted JSON** file.
3.  **Place the file:** Place your exported JSON file (e.g., `my_export.json`) in the same directory as `vw_cleaner.py`.

---

## 🚀 Usage

The script supports two main modes: **Command Line Interface (CLI) / Batch Mode** and **Interactive Mode**.

### 1. CLI / Batch Mode (Recommended)

Specify the input file name as the first positional argument. The output and deleted files will be named automatically with the current date, ensuring previous runs are not overwritten.

**Standard Usage (Automatic Naming):**

```bash
python3 vw_cleaner.py my_export.json
```

Example Output Files (if run on 2025-11-26):
```bash
my_export.json.20251126_HHMMSS.bak

bitwarden_cleaned_20251126.json

bitwarden_deleted_20251126.json

merge_log_20251126.txt
```
Custom Output Filenames:

You can optionally specify the output (-o or --output) and deleted (-d or --deleted) file names.

```bash

python3 vw_cleaner.py my_export.json -o vault_latest.json -d my_removed_entries.json
```
2. Interactive Mode
Run the script without any arguments. It will prompt you for the necessary file names, offering intelligent defaults (including the date).

```bash

python3 vw_cleaner.py
```
Example Prompt Dialogue:
```bash
=== Bitwarden/Vaultwarden Cleaner v3.0 ===
[HH:MM:SS] Backup of safety created: bitwarden_export_file.json.20251126_185030.bak
[HH:MM:SS] Loaded 1500 items.
Nome file input [bitwarden_export_file.json]: my_export.json
Nome file output [bitwarden_cleaned_20251126.json]: 
Nome file deleted [bitwarden_deleted_20251126.json]: 
...
```

💡 Deduplication Logic Explained
The primary goal is to identify entries that are genuinely duplicates (meaning the same login for the same service) and consolidate them, preserving all non-conflicting data.

An item is considered a duplicate and merged if ALL the following conditions are met:

Item Type: Both items are of type Login (Type 1).

Credentials Match: They have the exact same username AND password.

Site Relevance: They share at least one common URI (after normalization, which handles https://site.com/ and site.com equally) OR one of the items has no URIs (suggesting it's a general/orphan entry that should be absorbed).

The item with the most recent revisionDate is chosen as the Master Item, and the older duplicate's data is merged into it before the duplicate is moved to the deleted file.
