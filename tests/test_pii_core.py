"""Unit tests for pii_core.py

Run with:
    python -m pytest tests/test_pii_core.py -v
"""

import os
import sys
import hashlib
from unittest.mock import ANY
import pytest
import logging
import json
import re

# Add app/ directory to the path so that`import pii_core` works
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src/medimask-app/utils"))

import pii_core

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# purify_llm_output
# ─────────────────────────────────────────────────────────────────────────────

class TestPurifyLLMOutput:

    def test_empty_json_returns_empty_dict(self):
        """Empty JSON input should return an empty dict."""
        result = pii_core.purify_llm_output("{}")
        assert result == {}

    def test_empty_string_returns_empty_dict(self):
        """Empty string input should return an empty dict."""
        result = pii_core.purify_llm_output("")
        assert result == {}

    def test_whitespace_string_returns_empty_dict(self):
        """Whitespace-only string should return an empty dict."""
        result = pii_core.purify_llm_output("   \n\t  ")
        assert result == {}

    def test_does_not_modify_original_input(self):
        """The original JSON string should not be modified by the function. (Proof of pure function)"""
        original_llm_output = '{"names": ["山田太郎"], "locations": ["東京都"]}'
        json_copy = original_llm_output  # Make a copy for comparison
        pii_core.purify_llm_output(original_llm_output)
        assert original_llm_output == json_copy  # Original string should remain unchanged

    def test_valid_llm_output_returns_dict(self):
        """Valid JSON string should be parsed into a dict."""
        json_str = '{"names": ["山田太郎"], "locations": []}'
        result = pii_core.purify_llm_output(json_str)
        assert result == {"names": ["山田太郎"], "locations": []}

    def test_invalid_json_with_no_closing_brace_returns_empty_dict(self):
        """Invalid JSON should return an empty dict."""
        invalid_llm_output = '{"names": ["山田太郎"], "locations": ["東京都"}'  # Missing closing brace
        result = pii_core.purify_llm_output(invalid_llm_output)
        assert result == {}

    def test_invalid_json_with_added_comma_returns_empty_dict(self):
        """Invalid JSON should return an empty dict."""
        invalid_llm_output = '{"names": ["山田太郎"], "locations": ["東京都"],}'  # Added comma
        result = pii_core.purify_llm_output(invalid_llm_output)
        assert result == {}

    def test_pii_is_dict_even_when_provided_list(self):
        """purify_llm_output must always return a dict, even if the JSON is valid."""
        json_str = '["山田太郎","鈴木花子"]'
        result = pii_core.purify_llm_output(json_str)
        assert isinstance(result, dict)

    def test_handles_nested_empty_lists(self):
        """Should handle nested structures with empty lists correctly."""
        json_str = '{"names": [], "locations": [], "hospitals": [], "identifiers": [], "dates": []}'
        expected = {"names": [], "locations": [], "hospitals": [], "identifiers": [], "dates": []}
        result = pii_core.purify_llm_output(json_str)
        assert result == expected

    def test_json_with_blanks_and_spaces_can_be_parsed_correctly(self):
        expected = {"names": ["山田太郎"], "locations": ["東京都"], "hospitals": [], "identifiers": [], "dates": []}
        json_str = ' {"names": ["山田太郎"], "locations": ["東京都"], "hospitals": [], "identifiers": [], "dates": []} '
        result = pii_core.purify_llm_output(json_str)
        assert result == expected
        json_str = '\n {"names": ["山田太郎"], "locations": ["東京都"], "hospitals": [], "identifiers": [], "dates": []} \n'
        result = pii_core.purify_llm_output(json_str)
        assert result == expected

    def test_backquoted_json_can_be_parsed_correctly(self):
        """Backquoted JSON should be parsed into a dict."""
        expected = {"names": ["山田太郎"], "locations": ["東京都"]}
        json_str = '```json{"names": ["山田太郎"], "locations": ["東京都"]}```'
        result = pii_core.purify_llm_output(json_str)
        assert result == expected
        json_str = '```{"names": ["山田太郎"], "locations": ["東京都"]}```'
        result = pii_core.purify_llm_output(json_str)
        assert result == expected
        json_str = '```json\n{"names": ["山田太郎"], "locations": ["東京都"]}\n```'
        result = pii_core.purify_llm_output(json_str)
        assert result == expected
        json_str = '```\n{"names": ["山田太郎"], "locations": ["東京都"]}\n```'
        result = pii_core.purify_llm_output(json_str)
        assert result == expected

# ─────────────────────────────────────────────────────────────────────────────
# enforce_pii_schema
# ─────────────────────────────────────────────────────────────────────────────

class TestEnforcePIISchema:

    def test_empty_input_to_skeleton_dict(self):
        input_dict = {}
        expected_dict = {
            "names": [],
            "locations": [],
            "hospitals": [],
            "identifiers": [],
            "dates": []
        }
        result_dict = pii_core.enforce_pii_schema(input_dict)
        assert result_dict == expected_dict

    def test_missing_keys_are_added_with_blank_lists(self):
        input_dict = {
            "names": ["山田太郎", "Dr.黒川"],
            "hospitals": ["東雲レディスクリニック"],
        }
        expected_dict = {
            "names": ["山田太郎", "Dr.黒川"],
            "locations": [],
            "hospitals": ["東雲レディスクリニック"],
            "identifiers": [],
            "dates": []
        }
        result_dict = pii_core.enforce_pii_schema(input_dict)
        assert result_dict == expected_dict

    def test_string_element_is_converted_to_list(self):
        input_dict = {
            "names": "山田太郎",
            "hospitals": "東雲レディスクリニック",
        }
        expected_dict = {
            "names": ["山田太郎"],
            "locations": [],
            "hospitals": ["東雲レディスクリニック"],
            "identifiers": [],
            "dates": []
        }
        result_dict = pii_core.enforce_pii_schema(input_dict)
        assert result_dict == expected_dict

    def test_unknown_keys_are_removed(self):
        input_dict = {
            "names": [],
            "locations": [],
            "hospitals": [],
            "identifiers": [],
            "dates": [],
            "unknown_key": ["unknown_value"]
        }
        expected_dict = {
            "names": [],
            "locations": [],
            "hospitals": [],
            "identifiers": [],
            "dates": []
        }
        result_dict = pii_core.enforce_pii_schema(input_dict)
        assert result_dict == expected_dict

# ─────────────────────────────────────────────────────────────────────────────
# build_replacement_list
# ─────────────────────────────────────────────────────────────────────────────
class TestBuildReplacementList:

    def test_return_skeleton_ReplacementList_when_provided_blank_text_and_skeleton_pii(self):
        result = pii_core.build_replacement_list("", {
            "names": [],
            "locations": [],
            "hospitals": [],
            "identifiers": [],
            "dates": []
        })
        assert result == {
            "text_hash": hashlib.sha256("".encode()).hexdigest(),
            "status": "Unconfirmed",
            "created_at": ANY,
            "replacements": []
        }

    def test_return_single_pii_replacement_list(self):
        raw_text="患者は山田小太郎です。"
        result = pii_core.build_replacement_list(raw_text, {
            "names": ["山田小太郎"],
            "locations": [],
            "hospitals": [],
            "identifiers": [],
            "dates": []
        })
        assert result == {
            "text_hash": hashlib.sha256(raw_text.encode()).hexdigest(),
            "status": "Unconfirmed",
            "created_at": ANY,
            "replacements": [
                {
                    "id": ANY,
                    "type": "name",
                    "start": 3,
                    "length": 5,
                    "method": "auto"
                }
            ]
        }

    def test_return_multiple_pii_replacement_list(self):
        raw_text="患者は山田小太郎で、住所は東京都千代田区外神田2-2-6です。"
        result = pii_core.build_replacement_list(raw_text, {
            "names": ["山田小太郎"],
            "locations": ["東京都千代田区外神田2-2-6"],
            "hospitals": [],
            "identifiers": [],
            "dates": []
        })
        assert result == {
            "text_hash": hashlib.sha256(raw_text.encode()).hexdigest(),
            "status": "Unconfirmed",
            "created_at": ANY,
            "replacements": [
                {
                    "id": ANY,
                    "type": "name",
                    "start": 3,
                    "length": 5,
                    "method": "auto"
                },
                {
                    "id": ANY,
                    "type": "location",
                    "start": 13,
                    "length": 15,
                    "method": "auto"
                }
            ]
        }

    def test_return_overlapping_pii_replacement_list(self):
        raw_text="住所は東京都千代田区外神田2-2-6。東京都には20年間在住。"
        result = pii_core.build_replacement_list(raw_text, {
            "names": [],
            "locations": ["東京都", "東京都千代田区外神田2-2-6"],
            "hospitals": [],
            "identifiers": [],
            "dates": []
        })
        assert result == {
            "text_hash": hashlib.sha256(raw_text.encode()).hexdigest(),
            "status": "Unconfirmed",
            "created_at": ANY,
            "replacements": [
                {
                    "id": ANY,
                    "type": "location",
                    "start": 3,
                    "length": 15,
                    "method": "auto"
                },
                {
                    "id": ANY,
                    "type": "location",
                    "start": 19,
                    "length": 3,
                    "method": "auto"
                }
            ]
        }

    def test_return_proximity_pii_replacement_list(self):
        raw_text="患者は東京都渋谷区リハビリテーションセンターのレクリエーション室にて転倒"
        result = pii_core.build_replacement_list(raw_text, {
            "names": [],
            "locations": ["東京都"],
            "hospitals": ["渋谷区リハビリテーションセンター"],
            "identifiers": [],
            "dates": []
        })
        assert result == {
            "text_hash": hashlib.sha256(raw_text.encode()).hexdigest(),
            "status": "Unconfirmed",
            "created_at": ANY,
            "replacements": [
                {
                    "id": ANY,
                    "type": "location",
                    "start": 3,
                    "length": 3,
                    "method": "auto"
                },
                {
                    "id": ANY,
                    "type": "hospital",
                    "start": 6,
                    "length": 16,
                    "method": "auto"
                }
            ]
        }

    def test_return_2_partially_overlapping_pii_replacement_list(self):
        raw_text="患者は東京都渋谷区リハビリテーションセンターのレクリエーション室にて転倒"
        result = pii_core.build_replacement_list(raw_text, {
            "names": [],
            "locations": ["東京都渋谷区"],
            "hospitals": ["渋谷区リハビリテーションセンター"],
            "identifiers": [],
            "dates": []
        })
        assert result == {
            "text_hash": hashlib.sha256(raw_text.encode()).hexdigest(),
            "status": "Unconfirmed",
            "created_at": ANY,
            "replacements": [
                {
                    "id": ANY,
                    "type": "hospital",
                    "start": 3,
                    "length": 19,
                    "method": "auto"
                }
            ]
        }

    def test_return_3_partially_overlapping_pii_replacement_list(self):
        raw_text="患者は東京都渋谷区リハビリテーションセンター駅前の階段で転倒"
        result = pii_core.build_replacement_list(raw_text, {
            "names": [],
            "locations": ["東京都渋谷区","リハビリテーションセンター駅"],
            "hospitals": ["渋谷区リハビリテーションセンター"],
            "identifiers": [],
            "dates": []
        })
        assert result == {
            "text_hash": hashlib.sha256(raw_text.encode()).hexdigest(),
            "status": "Unconfirmed",
            "created_at": ANY,
            "replacements": [
                {
                    "id": ANY,
                    "type": "hospital",
                    "start": 3,
                    "length": 20,
                    "method": "auto"
                }
            ]
        }

# ─────────────────────────────────────────────────────────────────────────────
# mask_pii
# ─────────────────────────────────────────────────────────────────────────────
class TestMaskPII:

    def test_with_no_replacement(self):
        raw_text = "患者は心筋梗塞の疑い"
        metadata = {
            "text_hash": hashlib.sha256(raw_text.encode()).hexdigest(),
            "status": "Unconfirmed",
            "created_at": ANY,
            "replacements": []
        }
        result = pii_core.mask_pii(raw_text, metadata)
        assert result == raw_text

    def test_with_single_replacement(self):
        raw_text = "患者は山田小太郎です。"
        metadata = {
            "text_hash": hashlib.sha256(raw_text.encode()).hexdigest(),
            "status": "Unconfirmed",
            "created_at": ANY,
            "replacements": [
                {
                    "id": ANY,
                    "type": "name",
                    "start": 3,
                    "length": 5,
                    "method": "auto"
                }
            ]
        }
        result = pii_core.mask_pii(raw_text, metadata)
        expected = "患者は[MASKED]です。"
        assert result == expected

    def test_with_multiple_replacements(self):
        raw_text = "患者は山田小太郎で、住所は東京都千代田区外神田2-2-6です。"
        metadata = {
            "text_hash": hashlib.sha256(raw_text.encode()).hexdigest(),
            "status": "Unconfirmed",
            "created_at": ANY,
            "replacements": [
                {
                    "id": ANY,
                    "type": "name",
                    "start": 3,
                    "length": 5,
                    "method": "auto"
                },
                {
                    "id": ANY,
                    "type": "location",
                    "start": 13,
                    "length": 15,
                    "method": "auto"
                }
            ]
        }
        result = pii_core.mask_pii(raw_text, metadata)
        expected = "患者は[MASKED]で、住所は[MASKED]です。"
        assert result == expected

    def test_hash_mismatch(self):
        raw_text = "住所は東京都千代田区外神田2-2-6。東京都には20年間在住。"
        metadata = {
            "text_hash": hashlib.sha256("dummy text".encode()).hexdigest(),
            "status": "Unconfirmed",
            "created_at": ANY,
            "replacements": [
                {
                    "id": ANY,
                    "type": "location",
                    "start": 3,
                    "length": 15,
                    "method": "auto"
                },
                {
                    "id": ANY,
                    "type": "location",
                    "start": 19,
                    "length": 3,
                    "method": "auto"
                }
            ]
        }
        with pytest.raises(ValueError) as e:
            pii_core.mask_pii(raw_text, metadata)
        assert "Text hash mismatch. Invalid replacement metadata for this raw text." == str(e.value)

# ─────────────────────────────────────────────────────────────────────────────
# Integration Test
# ─────────────────────────────────────────────────────────────────────────────

def format_json_compact_lists(data: dict) -> str:
    """Format JSON but keep single-element lists on one line."""
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    # Collapse lists that contain a single string or number
    return re.sub(r'\[\s*("[^"]*"|\d+)\s*\]', r'[\1]', json_str)

class TestPIICoreIntegration:
    def test_full_pipeline_from_llm_to_masked_text(self):
        """Test entire pipeline from extract_pii_with_retry to mask_pii"""
        raw_text = "患者の山田太郎は東京都新宿区に在住。"        
        llm_output = '```json\n{"names": "山田太郎", "locations": ["東京都新宿区"]}\n```'
        logger.info(f"Raw text: {raw_text}")
        logger.info(f"Simulated LLM output: {llm_output}")
        
        # Step 1: Cleanup LLM Output
        original_pii_dict = pii_core.purify_llm_output(llm_output)
        formatted_original_pii_dict = format_json_compact_lists(original_pii_dict)
        logger.info(f"Original PII dict:\n{formatted_original_pii_dict}")

        # Step 2: Enforce PII Schema
        pii_dict = pii_core.enforce_pii_schema(original_pii_dict)
        formatted_pii_dict = format_json_compact_lists(pii_dict)
        logger.info(f"Enforced PII dict:\n{formatted_pii_dict}")

        # Step 3: Create replacement metadata from extracted PII
        metadata = pii_core.build_replacement_list(raw_text, pii_dict)
        formatted_metadata = format_json_compact_lists(metadata)
        logger.info(f"Metadata:\n{formatted_metadata}")
        
        # Step 4: Mask the text
        final_text = pii_core.mask_pii(raw_text, metadata)
        logger.info(f"Final text: {final_text}")
        
        # Step 5: Assert the final output
        assert final_text == "患者の[MASKED]は[MASKED]に在住。"
        
        # (Extra) Assert metadata status
        assert metadata["status"] == "Unconfirmed"