"""Unit tests for llm_client.py

Run with:
    python -m pytest tests/test_llm_client.py -v
"""

import os
import sys
from unittest.mock import MagicMock
import pytest
# Add app/ directory to the path so that`import pii_core` works
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src/medimask-app/utils"))

import llm_client
import pii_core

# ─────────────────────────────────────────────────────────────────────────────
# extract_pii_with_retry
# ─────────────────────────────────────────────────────────────────────────────
class TestExtractPIIWithRetry:

    def test_return_skeleton_dict_when_llm_raise_api_error(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        result = llm_client.extract_pii_with_retry("", client=mock_client)
        assert result == {
            "names": [],
            "locations": [],
            "hospitals": [],
            "identifiers": [],
            "dates": []
        }
    def test_blank_user_prompt_results_in_skeleton_dict(self):
        """Blank text input should results in skeleton dict."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{}'
        mock_client.chat.completions.create.return_value = mock_response
        result = llm_client.extract_pii_with_retry("", client=mock_client)
        assert result == {
            "names": [],
            "locations": [],
            "hospitals": [],
            "identifiers": [],
            "dates": []
        }

    def test_user_prompt_with_name_detection(self):
        """User prompt with name should result in correct PII dict."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        # Missing keys and dirty text test
        mock_response.choices[0].message.content = '```json\n{"names": ["山田太郎"]}\n```'
        mock_client.chat.completions.create.return_value = mock_response
        result = llm_client.extract_pii_with_retry("患者の名前は山田太郎。", client=mock_client)
        assert result == {
            "names": ["山田太郎"],
            "locations": [],
            "hospitals": [],
            "identifiers": [],
            "dates": []
        }

    def test_user_prompt_with_multiple_pii_detection(self):
        """User prompt with multiple PII should result in correct PII dict."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        # Unordered keys test
        mock_response.choices[0].message.content = '''{
            "hospitals": ["麹町四丁目クリニック"],
            "names": ["山田太郎"],
            "locations": ["千葉県四街道市大日2丁目3-14"]
            }'''
        mock_client.chat.completions.create.return_value = mock_response
        result = llm_client.extract_pii_with_retry("患者の名前は山田太郎。住所は千葉県四街道市大日2丁目3-14。麹町四丁目クリニックからの紹介で来院。主症状は腫脹および膨満感。", client=mock_client)
        assert result == {
            "names": ["山田太郎"],
            "locations": ["千葉県四街道市大日2丁目3-14"],
            "hospitals": ["麹町四丁目クリニック"],
            "identifiers": [],
            "dates": []
        }