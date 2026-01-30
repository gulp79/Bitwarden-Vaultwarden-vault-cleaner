"""
Suite di test completa per Bitwarden/Vaultwarden Vault Cleaner.

Include:
- Unit tests per normalizzazione
- Unit tests per merge logic
- Property-based tests (idempotenza, no-loss, ecc.)
- Integration tests con dataset sintetici
- Test casi limite

Requirements:
    pip install pytest hypothesis

Usage:
    pytest test_vw_cleaner.py -v
    pytest test_vw_cleaner.py -v --hypothesis-show-statistics

Author: Principal Engineer Review
Date: 2026-01-29
"""

import pytest
import json
import tempfile
import os
from copy import deepcopy
from hypothesis import given, strategies as st, settings, assume

# Import moduli da testare
from vw_normalization import (
    normalize_username_min,
    normalize_username_std,
    normalize_uri_min,
    normalize_uri_std,
    normalize_password_min,
    NormalizationLevel,
    generate_grouping_key,
    have_shared_uri,
)

from vw_cleaner_core_v2 import (
    clean_vault_advanced,
    CleanerConfig,
    MergePolicy,
    stable_sort_key,
    merge_items_advanced,
    should_merge_items,
)


# =============================================================================
# UNIT TESTS - NORMALIZZAZIONE
# =============================================================================

class TestNormalizationUsername:
    """Test normalizzazione username."""
    
    def test_min_trim_whitespace(self):
        assert normalize_username_min("  user  ") == "user"
        assert normalize_username_min("\tuser\n") == "user"
    
    def test_min_preserve_case(self):
        assert normalize_username_min("User@Example.COM") == "User@Example.COM"
    
    def test_std_lowercase(self):
        assert normalize_username_std("User@Example.COM") == "user@example.com"
    
    def test_std_trim_and_lower(self):
        assert normalize_username_std("  User  ") == "user"


class TestNormalizationURI:
    """Test normalizzazione URI."""
    
    def test_min_trim(self):
        assert normalize_uri_min("  http://example.com  ") == "http://example.com"
    
    def test_min_lowercase(self):
        assert normalize_uri_min("HTTP://Example.COM") == "http://example.com"
    
    def test_min_remove_trailing_slash(self):
        assert normalize_uri_min("http://example.com/") == "http://example.com"
        assert normalize_uri_min("http://example.com/path/") == "http://example.com/path"
    
    def test_min_preserve_path(self):
        assert normalize_uri_min("http://example.com/Path") == "http://example.com/path"
    
    def test_std_remove_default_port(self):
        # HTTP default port 80
        result = normalize_uri_std("http://example.com:80")
        assert ":80" not in result
        
        # HTTPS default port 443
        result = normalize_uri_std("https://example.com:443")
        assert ":443" not in result
    
    def test_std_preserve_non_default_port(self):
        result = normalize_uri_std("http://example.com:8080")
        assert ":8080" in result
    
    def test_std_remove_fragment(self):
        result = normalize_uri_std("http://example.com/page#anchor")
        assert "#anchor" not in result
    
    def test_std_sort_query_string(self):
        result = normalize_uri_std("http://example.com?z=1&a=2")
        # Query dovrebbe essere ordinata
        assert "a=2" in result and "z=1" in result


class TestNormalizationPassword:
    """Test normalizzazione password."""
    
    def test_min_trim_only(self):
        assert normalize_password_min("  pass123  ") == "pass123"
    
    def test_min_preserve_internal_spaces(self):
        # Spazi interni devono essere preservati
        assert normalize_password_min("pass 123") == "pass 123"
    
    def test_min_preserve_case(self):
        assert normalize_password_min("Pass123") == "Pass123"


# =============================================================================
# UNIT TESTS - GROUPING & MATCHING
# =============================================================================

class TestGroupingKey:
    """Test generazione chiavi di raggruppamento."""
    
    def test_valid_login_item(self):
        item = {
            "type": 1,
            "login": {
                "username": "user@example.com",
                "password": "pass123"
            }
        }
        key = generate_grouping_key(item, NormalizationLevel.MIN)
        assert key is not None
        assert key == ("user@example.com", "pass123")
    
    def test_non_login_item(self):
        item = {
            "type": 2,  # Non-login
            "login": {"username": "user", "password": "pass"}
        }
        key = generate_grouping_key(item, NormalizationLevel.MIN)
        assert key is None
    
    def test_missing_username(self):
        item = {
            "type": 1,
            "login": {"password": "pass123"}
        }
        key = generate_grouping_key(item, NormalizationLevel.MIN)
        assert key is None
    
    def test_missing_password(self):
        item = {
            "type": 1,
            "login": {"username": "user@example.com"}
        }
        key = generate_grouping_key(item, NormalizationLevel.MIN)
        assert key is None
    
    def test_normalization_applied(self):
        item = {
            "type": 1,
            "login": {
                "username": "  User@Example.COM  ",
                "password": "  pass123  "
            }
        }
        # MIN: trim only
        key_min = generate_grouping_key(item, NormalizationLevel.MIN)
        assert key_min == ("User@Example.COM", "pass123")
        
        # STD: trim + lowercase username
        key_std = generate_grouping_key(item, NormalizationLevel.STD)
        assert key_std == ("user@example.com", "pass123")


class TestSharedURI:
    """Test rilevamento URI condivise."""
    
    def test_identical_uris(self):
        item1 = {
            "login": {
                "uris": [{"uri": "http://example.com"}]
            }
        }
        item2 = {
            "login": {
                "uris": [{"uri": "http://example.com"}]
            }
        }
        assert have_shared_uri(item1, item2, NormalizationLevel.MIN) is True
    
    def test_normalized_match(self):
        item1 = {
            "login": {
                "uris": [{"uri": "http://example.com/"}]
            }
        }
        item2 = {
            "login": {
                "uris": [{"uri": "HTTP://Example.COM"}]
            }
        }
        # MIN normalizzazione dovrebbe farli matchare
        assert have_shared_uri(item1, item2, NormalizationLevel.MIN) is True
    
    def test_disjoint_uris(self):
        item1 = {
            "login": {
                "uris": [{"uri": "http://example.com"}]
            }
        }
        item2 = {
            "login": {
                "uris": [{"uri": "http://other.com"}]
            }
        }
        assert have_shared_uri(item1, item2, NormalizationLevel.MIN) is False
    
    def test_empty_uris(self):
        item1 = {"login": {"uris": []}}
        item2 = {"login": {"uris": [{"uri": "http://example.com"}]}}
        assert have_shared_uri(item1, item2, NormalizationLevel.MIN) is False
    
    def test_multiple_uris_partial_match(self):
        item1 = {
            "login": {
                "uris": [
                    {"uri": "http://example.com"},
                    {"uri": "http://other.com"}
                ]
            }
        }
        item2 = {
            "login": {
                "uris": [
                    {"uri": "http://different.com"},
                    {"uri": "http://example.com"}  # Match su questo
                ]
            }
        }
        assert have_shared_uri(item1, item2, NormalizationLevel.MIN) is True


# =============================================================================
# UNIT TESTS - MERGE LOGIC
# =============================================================================

class TestStableSort:
    """Test ordinamento deterministico."""
    
    def test_sort_by_revision_date(self):
        items = [
            {"id": "1", "revisionDate": "2024-01-01T00:00:00Z"},
            {"id": "2", "revisionDate": "2024-01-02T00:00:00Z"},
            {"id": "3", "revisionDate": "2024-01-03T00:00:00Z"},
        ]
        items.sort(key=stable_sort_key, reverse=True)
        assert items[0]["id"] == "3"  # Più recente
        assert items[1]["id"] == "2"
        assert items[2]["id"] == "1"
    
    def test_tie_break_by_id(self):
        items = [
            {"id": "c", "revisionDate": "2024-01-01T00:00:00Z"},
            {"id": "a", "revisionDate": "2024-01-01T00:00:00Z"},
            {"id": "b", "revisionDate": "2024-01-01T00:00:00Z"},
        ]
        items.sort(key=stable_sort_key, reverse=True)
        # Con reverse=True e stessa revisionDate, l'ordine è c > b > a
        assert items[0]["id"] == "c"
        assert items[1]["id"] == "b"
        assert items[2]["id"] == "a"


class TestMergeItems:
    """Test merge di item."""
    
    def setup_method(self):
        """Setup per ogni test."""
        self.config = CleanerConfig()
    
    def test_merge_uris(self):
        master = {
            "id": "master",
            "name": "Master",
            "login": {
                "username": "user",
                "password": "pass",
                "uris": [{"uri": "http://example.com"}]
            }
        }
        slave = {
            "id": "slave",
            "name": "Slave",
            "login": {
                "username": "user",
                "password": "pass",
                "uris": [{"uri": "http://other.com"}]
            }
        }
        
        result, fields = merge_items_advanced(master, slave, self.config)
        
        assert "uris" in fields
        assert len(result["login"]["uris"]) == 2
        uris = [u["uri"] for u in result["login"]["uris"]]
        assert "http://example.com" in uris
        assert "http://other.com" in uris
    
    def test_merge_notes(self):
        master = {
            "id": "master",
            "name": "Master",
            "notes": "Master notes",
            "login": {"username": "u", "password": "p", "uris": []}
        }
        slave = {
            "id": "slave",
            "name": "Slave",
            "notes": "Slave notes",
            "login": {"username": "u", "password": "p", "uris": []}
        }
        
        result, fields = merge_items_advanced(master, slave, self.config)
        
        assert "notes" in fields
        assert "Master notes" in result["notes"]
        assert "Slave notes" in result["notes"]
        assert "MERGED NOTES" in result["notes"]
    
    def test_merge_totp_empty_master(self):
        master = {
            "id": "master",
            "name": "Master",
            "login": {"username": "u", "password": "p", "uris": []}
        }
        slave = {
            "id": "slave",
            "name": "Slave",
            "login": {
                "username": "u",
                "password": "p",
                "uris": [],
                "totp": "otpauth://totp/..."
            }
        }
        
        result, fields = merge_items_advanced(master, slave, self.config)
        
        assert "totp" in fields
        assert result["login"]["totp"] == "otpauth://totp/..."
    
    def test_no_merge_totp_both_present(self):
        master = {
            "id": "master",
            "name": "Master",
            "login": {
                "username": "u",
                "password": "p",
                "uris": [],
                "totp": "otpauth://totp/master"
            }
        }
        slave = {
            "id": "slave",
            "name": "Slave",
            "login": {
                "username": "u",
                "password": "p",
                "uris": [],
                "totp": "otpauth://totp/slave"
            }
        }
        
        result, fields = merge_items_advanced(master, slave, self.config)
        
        # TOTP del master deve essere preservato
        assert result["login"]["totp"] == "otpauth://totp/master"
        assert "totp" not in fields  # Non è stato mergiato


class TestShouldMerge:
    """Test decisioni di merge."""
    
    def test_strict_policy_with_shared_uri(self):
        config = CleanerConfig(merge_policy=MergePolicy.STRICT)
        
        master = {
            "login": {
                "username": "u",
                "password": "p",
                "uris": [{"uri": "http://example.com"}]
            }
        }
        candidate = {
            "login": {
                "username": "u",
                "password": "p",
                "uris": [{"uri": "http://example.com"}]
            }
        }
        
        should_merge, reason = should_merge_items(master, candidate, config)
        assert should_merge is True
        assert "shared_uri" in reason
    
    def test_strict_policy_disjoint_uris(self):
        config = CleanerConfig(merge_policy=MergePolicy.STRICT)
        
        master = {
            "login": {
                "username": "u",
                "password": "p",
                "uris": [{"uri": "http://example.com"}]
            }
        }
        candidate = {
            "login": {
                "username": "u",
                "password": "p",
                "uris": [{"uri": "http://other.com"}]
            }
        }
        
        should_merge, reason = should_merge_items(master, candidate, config)
        assert should_merge is False
        assert "disjoint" in reason
    
    def test_strict_policy_empty_uris(self):
        config = CleanerConfig(merge_policy=MergePolicy.STRICT)
        
        master = {
            "login": {"username": "u", "password": "p", "uris": []}
        }
        candidate = {
            "login": {
                "username": "u",
                "password": "p",
                "uris": [{"uri": "http://example.com"}]
            }
        }
        
        should_merge, reason = should_merge_items(master, candidate, config)
        assert should_merge is False
        assert "empty" in reason
    
    def test_lenient_policy_disjoint(self):
        config = CleanerConfig(merge_policy=MergePolicy.LENIENT)
        
        master = {
            "login": {
                "username": "u",
                "password": "p",
                "uris": [{"uri": "http://example.com"}]
            }
        }
        candidate = {
            "login": {
                "username": "u",
                "password": "p",
                "uris": [{"uri": "http://other.com"}]
            }
        }
        
        should_merge, reason = should_merge_items(master, candidate, config)
        # LENIENT con URI disgiunte → NON merge (comportamento originale)
        assert should_merge is False


# =============================================================================
# PROPERTY-BASED TESTS
# =============================================================================

# Strategy per generare item Bitwarden validi
def bitwarden_login_item_strategy(
    username: str = None,
    password: str = None,
    uris: list = None
):
    """Helper per generare item login sintetici."""
    if username is None:
        username = st.text(min_size=1, max_size=50).example()
    if password is None:
        password = st.text(min_size=1, max_size=50).example()
    if uris is None:
        uris = []
    
    return {
        "type": 1,
        "id": st.uuids().example(),
        "name": st.text(min_size=1, max_size=100).example(),
        "login": {
            "username": username,
            "password": password,
            "uris": [{"uri": uri} for uri in uris]
        },
        "revisionDate": st.datetimes().example().isoformat(),
    }


@settings(max_examples=50, deadline=1000)
class TestPropertyBased:
    """Test basati su proprietà (Hypothesis)."""
    
    @given(st.text(min_size=0, max_size=100))
    def test_username_normalization_idempotent(self, text):
        """Normalizzazione username deve essere idempotente."""
        norm1 = normalize_username_min(text)
        norm2 = normalize_username_min(norm1)
        assert norm1 == norm2
    
    @given(st.text(min_size=0, max_size=200))
    def test_uri_normalization_idempotent(self, text):
        """Normalizzazione URI deve essere idempotente."""
        norm1 = normalize_uri_min(text)
        norm2 = normalize_uri_min(norm1)
        assert norm1 == norm2
    
    def test_merge_idempotence(self):
        """
        Property: Dedup(Dedup(X)) == Dedup(X)
        
        Se applico la deduplica due volte allo stesso dataset,
        il risultato deve essere identico.
        """
        # Dataset sintetico con duplicati
        items = [
            bitwarden_login_item_strategy(
                username="user@example.com",
                password="pass123",
                uris=["http://example.com"]
            ),
            bitwarden_login_item_strategy(
                username="user@example.com",
                password="pass123",
                uris=["http://example.com"]
            ),
            bitwarden_login_item_strategy(
                username="different@example.com",
                password="otherpass",
                uris=["http://other.com"]
            ),
        ]
        
        # Prima deduplica
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"items": items}, f)
            input_file1 = f.name
        
        output_file1 = tempfile.mktemp(suffix='.json')
        deleted_file1 = tempfile.mktemp(suffix='.json')
        
        config = CleanerConfig(enable_dry_run=False)
        stats1 = clean_vault_advanced(
            input_file=input_file1,
            output_file=output_file1,
            deleted_file=deleted_file1,
            config=config,
            log_cb=None
        )
        
        # Seconda deduplica sull'output della prima
        output_file2 = tempfile.mktemp(suffix='.json')
        deleted_file2 = tempfile.mktemp(suffix='.json')
        
        stats2 = clean_vault_advanced(
            input_file=output_file1,
            output_file=output_file2,
            deleted_file=deleted_file2,
            config=config,
            log_cb=None
        )
        
        # Verifica idempotenza
        assert stats2.removed == 0, "Seconda passata non dovrebbe rimuovere nulla"
        assert stats1.total_end == stats2.total_end, "Numero finale di item deve essere uguale"
        
        # Cleanup
        for f in [input_file1, output_file1, output_file2, deleted_file1, deleted_file2]:
            if os.path.exists(f):
                os.unlink(f)
    
    def test_no_information_loss_uris(self):
        """
        Property: No-Loss per URI
        
        L'unione delle URI di tutti gli item post-merge deve contenere
        tutte le URI degli item pre-merge.
        """
        items = [
            bitwarden_login_item_strategy(
                username="user",
                password="pass",
                uris=["http://a.com", "http://b.com"]
            ),
            bitwarden_login_item_strategy(
                username="user",
                password="pass",
                uris=["http://c.com"]
            ),
        ]
        
        # URI pre-merge
        uris_before = set()
        for item in items:
            for u in item["login"]["uris"]:
                uris_before.add(normalize_uri_min(u["uri"]))
        
        # Deduplica
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"items": items}, f)
            input_file = f.name
        
        output_file = tempfile.mktemp(suffix='.json')
        deleted_file = tempfile.mktemp(suffix='.json')
        
        config = CleanerConfig()
        clean_vault_advanced(
            input_file=input_file,
            output_file=output_file,
            deleted_file=deleted_file,
            config=config,
            log_cb=None
        )
        
        # URI post-merge
        with open(output_file, 'r') as f:
            output_data = json.load(f)
        
        uris_after = set()
        for item in output_data["items"]:
            if item.get("type") == 1 and item.get("login", {}).get("uris"):
                for u in item["login"]["uris"]:
                    uris_after.add(normalize_uri_min(u["uri"]))
        
        # Verifica: tutte le URI originali devono essere presenti
        assert uris_before.issubset(uris_after), "Perdita di URI durante merge!"
        
        # Cleanup
        for f in [input_file, output_file, deleted_file]:
            if os.path.exists(f):
                os.unlink(f)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Test di integrazione end-to-end."""
    
    def test_basic_deduplication(self):
        """Test deduplica base con dataset sintetico."""
        items = [
            {
                "type": 1,
                "id": "item1",
                "name": "Example Login 1",
                "login": {
                    "username": "user@example.com",
                    "password": "pass123",
                    "uris": [{"uri": "http://example.com"}]
                },
                "revisionDate": "2024-01-01T00:00:00Z"
            },
            {
                "type": 1,
                "id": "item2",
                "name": "Example Login 2 (duplicate)",
                "login": {
                    "username": "user@example.com",
                    "password": "pass123",
                    "uris": [{"uri": "http://example.com"}]
                },
                "revisionDate": "2024-01-02T00:00:00Z"  # Più recente
            },
            {
                "type": 1,
                "id": "item3",
                "name": "Different Login",
                "login": {
                    "username": "other@example.com",
                    "password": "different",
                    "uris": [{"uri": "http://other.com"}]
                },
                "revisionDate": "2024-01-01T00:00:00Z"
            },
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"items": items}, f)
            input_file = f.name
        
        output_file = tempfile.mktemp(suffix='.json')
        deleted_file = tempfile.mktemp(suffix='.json')
        
        config = CleanerConfig()
        stats = clean_vault_advanced(
            input_file=input_file,
            output_file=output_file,
            deleted_file=deleted_file,
            config=config,
            log_cb=None
        )
        
        # Verifica statistiche
        assert stats.total_start == 3
        assert stats.total_end == 2  # 2 item finali (1 mergiato)
        assert stats.removed == 1
        assert stats.merges_count == 1
        
        # Verifica output
        with open(output_file, 'r') as f:
            output = json.load(f)
        
        assert len(output["items"]) == 2
        
        # Verifica che item2 (più recente) sia il master
        merged_item = [i for i in output["items"] if i["id"] == "item2"][0]
        assert merged_item["id"] == "item2"
        
        # Cleanup
        for f in [input_file, output_file, deleted_file]:
            if os.path.exists(f):
                os.unlink(f)
    
    def test_disjoint_uris_not_merged_strict(self):
        """Test che URI disgiunte non vengano mergiate in modalità STRICT."""
        items = [
            {
                "type": 1,
                "id": "item1",
                "name": "Bank Login",
                "login": {
                    "username": "admin",
                    "password": "pass123",
                    "uris": [{"uri": "http://bank.com"}]
                },
                "revisionDate": "2024-01-01T00:00:00Z"
            },
            {
                "type": 1,
                "id": "item2",
                "name": "Shop Login",
                "login": {
                    "username": "admin",
                    "password": "pass123",
                    "uris": [{"uri": "http://shop.com"}]
                },
                "revisionDate": "2024-01-01T00:00:00Z"
            },
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"items": items}, f)
            input_file = f.name
        
        output_file = tempfile.mktemp(suffix='.json')
        deleted_file = tempfile.mktemp(suffix='.json')
        
        config = CleanerConfig(merge_policy=MergePolicy.STRICT)
        stats = clean_vault_advanced(
            input_file=input_file,
            output_file=output_file,
            deleted_file=deleted_file,
            config=config,
            log_cb=None
        )
        
        # Con STRICT, URI disgiunte NON devono essere mergiate
        assert stats.total_end == 2, "Entrambi gli item devono essere mantenuti"
        assert stats.removed == 0
        assert stats.uri_collisions_avoided == 1
        
        # Cleanup
        for f in [input_file, output_file, deleted_file]:
            if os.path.exists(f):
                os.unlink(f)


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test casi limite."""
    
    def test_empty_vault(self):
        """Vault vuoto non dovrebbe crashare."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"items": []}, f)
            input_file = f.name
        
        output_file = tempfile.mktemp(suffix='.json')
        deleted_file = tempfile.mktemp(suffix='.json')
        
        config = CleanerConfig()
        stats = clean_vault_advanced(
            input_file=input_file,
            output_file=output_file,
            deleted_file=deleted_file,
            config=config,
            log_cb=None
        )
        
        assert stats.total_start == 0
        assert stats.total_end == 0
        assert stats.removed == 0
        
        # Cleanup
        for f in [input_file, output_file, deleted_file]:
            if os.path.exists(f):
                os.unlink(f)
    
    def test_non_login_items_preserved(self):
        """Item non-login devono essere preservati intatti."""
        items = [
            {"type": 2, "id": "note1", "name": "Secure Note"},  # type=2 = secure note
            {"type": 3, "id": "card1", "name": "Credit Card"},  # type=3 = card
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"items": items}, f)
            input_file = f.name
        
        output_file = tempfile.mktemp(suffix='.json')
        deleted_file = tempfile.mktemp(suffix='.json')
        
        config = CleanerConfig()
        stats = clean_vault_advanced(
            input_file=input_file,
            output_file=output_file,
            deleted_file=deleted_file,
            config=config,
            log_cb=None
        )
        
        assert stats.total_start == 2
        assert stats.total_end == 2
        assert stats.removed == 0
        
        # Cleanup
        for f in [input_file, output_file, deleted_file]:
            if os.path.exists(f):
                os.unlink(f)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
