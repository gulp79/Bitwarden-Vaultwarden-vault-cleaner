"""
Micro-benchmark per Bitwarden/Vaultwarden Vault Cleaner.

Verifica complessità temporale O(N) con dataset sintetici di dimensione crescente.

Usage:
    python benchmark_vw_cleaner.py

Output:
    - Tabella con tempi di esecuzione per N crescente
    - Grafico tempo vs N (se matplotlib disponibile)
    - Verifica linearità tramite regressione lineare

Author: Principal Engineer Review
Date: 2026-01-29
"""

import json
import tempfile
import os
import time
import statistics
from typing import List, Tuple
import random
import string

from vw_cleaner_core_v2 import clean_vault_advanced, CleanerConfig, MergePolicy
from vw_normalization import NormalizationLevel


# =============================================================================
# SYNTHETIC DATA GENERATION
# =============================================================================

def generate_random_string(length: int = 10) -> str:
    """Genera stringa random alfanumerica."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_synthetic_vault(
    n_items: int,
    duplicate_ratio: float = 0.3,
    shared_uri_ratio: float = 0.5,
    seed: int = 42
) -> List[dict]:
    """
    Genera vault sintetico con caratteristiche controllate.
    
    Args:
        n_items: Numero totale di item da generare
        duplicate_ratio: Frazione di item che sono duplicati (0.0 - 1.0)
        shared_uri_ratio: Frazione di duplicati con URI condivise (0.0 - 1.0)
        seed: Random seed per riproducibilità
    
    Returns:
        Lista di item Bitwarden sintetici
    """
    random.seed(seed)
    items = []
    
    n_unique = int(n_items * (1 - duplicate_ratio))
    n_duplicates = n_items - n_unique
    
    # Pool di credenziali uniche
    unique_credentials = [
        (f"user{i}@example.com", f"pass{generate_random_string(8)}")
        for i in range(n_unique)
    ]
    
    # Genera item unici
    for i, (username, password) in enumerate(unique_credentials):
        item = {
            "type": 1,
            "id": f"unique-{i}",
            "name": f"Unique Item {i}",
            "login": {
                "username": username,
                "password": password,
                "uris": [{"uri": f"http://unique-{i}.example.com"}]
            },
            "revisionDate": f"2024-01-{(i % 28) + 1:02d}T10:00:00Z",
            "creationDate": f"2024-01-01T10:00:00Z",
        }
        items.append(item)
    
    # Genera duplicati
    duplicate_sources = random.choices(unique_credentials, k=n_duplicates)
    
    for i, (username, password) in enumerate(duplicate_sources):
        # Decidi se ha URI condivisa
        has_shared_uri = random.random() < shared_uri_ratio
        
        if has_shared_uri:
            # Trova l'item originale e riusa la sua URI
            original = next(
                (item for item in items if item["login"]["username"] == username),
                None
            )
            if original:
                uri = original["login"]["uris"][0]["uri"]
            else:
                uri = f"http://shared-{i}.example.com"
        else:
            # URI completamente diversa
            uri = f"http://different-{i}.example.com"
        
        item = {
            "type": 1,
            "id": f"duplicate-{i}",
            "name": f"Duplicate Item {i}",
            "login": {
                "username": username,
                "password": password,
                "uris": [{"uri": uri}]
            },
            "revisionDate": f"2024-01-{(i % 28) + 1:02d}T11:00:00Z",
            "creationDate": f"2024-01-01T11:00:00Z",
        }
        items.append(item)
    
    # Shuffle per evitare pattern evidenti
    random.shuffle(items)
    
    return items


# =============================================================================
# BENCHMARK EXECUTION
# =============================================================================

def run_single_benchmark(
    n_items: int,
    config: CleanerConfig,
    duplicate_ratio: float = 0.3,
    shared_uri_ratio: float = 0.5,
    n_runs: int = 3
) -> Tuple[float, dict]:
    """
    Esegue benchmark singolo con N item.
    
    Args:
        n_items: Numero di item
        config: Configurazione cleaner
        duplicate_ratio: Frazione duplicati
        shared_uri_ratio: Frazione con URI condivise
        n_runs: Numero di run per mediare il tempo
    
    Returns:
        Tupla (avg_time_ms, stats_dict)
    """
    times = []
    final_stats = None
    
    for run in range(n_runs):
        # Genera dataset
        items = generate_synthetic_vault(
            n_items=n_items,
            duplicate_ratio=duplicate_ratio,
            shared_uri_ratio=shared_uri_ratio,
            seed=42 + run  # Seed diverso per ogni run
        )
        
        # Scrivi su file temporaneo
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"items": items}, f)
            input_file = f.name
        
        output_file = tempfile.mktemp(suffix='.json')
        deleted_file = tempfile.mktemp(suffix='.json')
        
        # Misura tempo
        start = time.perf_counter()
        
        stats = clean_vault_advanced(
            input_file=input_file,
            output_file=output_file,
            deleted_file=deleted_file,
            config=config,
            log_cb=None,  # Silent
        )
        
        end = time.perf_counter()
        elapsed_ms = (end - start) * 1000
        times.append(elapsed_ms)
        
        if run == 0:
            final_stats = stats.to_dict()
        
        # Cleanup
        for f in [input_file, output_file, deleted_file]:
            if os.path.exists(f):
                os.unlink(f)
    
    avg_time = statistics.mean(times)
    return avg_time, final_stats


def run_benchmark_suite(
    sizes: List[int],
    config: CleanerConfig,
    duplicate_ratio: float = 0.3,
    n_runs: int = 3
) -> List[Tuple[int, float, dict]]:
    """
    Esegue suite completa di benchmark.
    
    Args:
        sizes: Lista di dimensioni N da testare
        config: Configurazione
        duplicate_ratio: Frazione duplicati
        n_runs: Numero di run per size
    
    Returns:
        Lista di tuple (n_items, avg_time_ms, stats)
    """
    results = []
    
    print("=" * 70)
    print("BENCHMARK SUITE - Bitwarden/Vaultwarden Vault Cleaner")
    print("=" * 70)
    print(f"Configuration:")
    print(f"  Normalization:  {config.normalization_level.value}")
    print(f"  Merge policy:   {config.merge_policy.value}")
    print(f"  Duplicate ratio: {duplicate_ratio * 100}%")
    print(f"  Runs per size:  {n_runs}")
    print("=" * 70)
    print()
    print(f"{'N Items':>10} | {'Time (ms)':>12} | {'Items/sec':>12} | {'Removed':>10} | {'Groups':>10}")
    print("-" * 70)
    
    for n in sizes:
        avg_time, stats = run_single_benchmark(
            n_items=n,
            config=config,
            duplicate_ratio=duplicate_ratio,
            n_runs=n_runs
        )
        
        items_per_sec = (n / avg_time) * 1000 if avg_time > 0 else 0
        
        print(f"{n:10,} | {avg_time:12.2f} | {items_per_sec:12.0f} | {stats['removed']:10} | {stats['groups_analyzed']:10}")
        
        results.append((n, avg_time, stats))
    
    print("=" * 70)
    print()
    
    return results


def analyze_complexity(results: List[Tuple[int, float, dict]]):
    """
    Analizza complessità tramite regressione lineare.
    
    Verifica se tempo ~ O(N) calculando coefficiente di determinazione R².
    """
    if len(results) < 3:
        print("Dati insufficienti per analisi complessità")
        return
    
    # Estrai N e tempi
    ns = [r[0] for r in results]
    times = [r[1] for r in results]
    
    # Calcola regressione lineare: time = a * N + b
    n_mean = statistics.mean(ns)
    time_mean = statistics.mean(times)
    
    # Slope (a)
    numerator = sum((n - n_mean) * (t - time_mean) for n, t in zip(ns, times))
    denominator = sum((n - n_mean) ** 2 for n in ns)
    slope = numerator / denominator if denominator != 0 else 0
    
    # Intercept (b)
    intercept = time_mean - slope * n_mean
    
    # Calcola R²
    predicted_times = [slope * n + intercept for n in ns]
    ss_res = sum((t - p) ** 2 for t, p in zip(times, predicted_times))
    ss_tot = sum((t - time_mean) ** 2 for t in times)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
    
    print("=" * 70)
    print("COMPLEXITY ANALYSIS")
    print("=" * 70)
    print(f"Linear regression: time = {slope:.6f} * N + {intercept:.2f}")
    print(f"R² (coefficient of determination): {r_squared:.4f}")
    print()
    
    if r_squared > 0.95:
        print("✅ EXCELLENT: Strong linear relationship (R² > 0.95)")
        print("   Complexity is confirmed O(N)")
    elif r_squared > 0.85:
        print("✅ GOOD: Linear relationship confirmed (R² > 0.85)")
        print("   Complexity is approximately O(N)")
    elif r_squared > 0.70:
        print("⚠️  MODERATE: Weak linear relationship (R² > 0.70)")
        print("   Complexity might have non-linear components")
    else:
        print("❌ POOR: Non-linear behavior detected (R² < 0.70)")
        print("   Complexity analysis inconclusive")
    
    print("=" * 70)
    print()


def plot_results(results: List[Tuple[int, float, dict]]):
    """
    Crea grafico tempo vs N (richiede matplotlib).
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("⚠️  matplotlib non disponibile - skip grafico")
        return
    
    ns = [r[0] for r in results]
    times = [r[1] for r in results]
    
    plt.figure(figsize=(10, 6))
    plt.plot(ns, times, 'bo-', linewidth=2, markersize=8, label='Measured')
    
    # Fit lineare
    n_mean = statistics.mean(ns)
    time_mean = statistics.mean(times)
    numerator = sum((n - n_mean) * (t - time_mean) for n, t in zip(ns, times))
    denominator = sum((n - n_mean) ** 2 for n in ns)
    slope = numerator / denominator if denominator != 0 else 0
    intercept = time_mean - slope * n_mean
    
    fitted = [slope * n + intercept for n in ns]
    plt.plot(ns, fitted, 'r--', linewidth=2, label=f'Linear fit (y = {slope:.4f}x + {intercept:.2f})')
    
    plt.xlabel('Number of Items (N)', fontsize=12)
    plt.ylabel('Processing Time (ms)', fontsize=12)
    plt.title('Vault Cleaner Performance - Time Complexity', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=11)
    
    # Salva
    output_file = "benchmark_results.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"📊 Grafico salvato: {output_file}")
    print()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Entry point principale."""
    
    # Configurazione benchmark
    config = CleanerConfig(
        normalization_level=NormalizationLevel.MIN,
        merge_policy=MergePolicy.LENIENT,
        enable_explain=False,
        enable_dry_run=False,
    )
    
    # Dimensioni da testare (progressione esponenziale)
    sizes = [100, 500, 1000, 2000, 5000, 10000]
    
    # Esegui benchmark
    results = run_benchmark_suite(
        sizes=sizes,
        config=config,
        duplicate_ratio=0.3,  # 30% duplicati
        n_runs=3,
    )
    
    # Analisi complessità
    analyze_complexity(results)
    
    # Plot (se disponibile)
    plot_results(results)
    
    print("✅ Benchmark completato")


if __name__ == "__main__":
    main()
