import os
import json
import logging
import re
import time
import hashlib
import uuid
from datetime import datetime, timezone
from typing import TypedDict, Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Type Hints
# ─────────────────────────────────────────
class ReplacementEntry(TypedDict):
    id: int # UUID 8 characters
    type: str # name, location, hospital, identifier, date
    start: int # start index of the token in the text by characters (not bytes)
    length: int # length of the token by characters (not bytes)
    method: str # Must be "auto" or "manual"

class ReplacementMetadata(TypedDict):
    text_hash: str
    status: str # Must be "Unconfirmed", "Excluded", or "Confirmed"
    created_at: str # ISO 8601 UTC format with seconds precision (no microsecond precision), e.g. 2026-05-09T05:25:06Z
    replacements: list[ReplacementEntry]

# ─────────────────────────────────────────
# Constants
# ─────────────────────────────────────────
EXPECTED_PII_KEYS = ["names", "locations", "hospitals", "identifiers", "dates"]

CATEGORY_TYPE_MAP: dict[str, str] = {
    "names":       "name",
    "locations":   "location",
    "hospitals":   "hospital",
    "identifiers": "identifier",
    "dates":       "date",
}

TYPE_PRIORITY = {
    "name": 1,
    "identifier": 2,
    "hospital": 3,
    "location": 4,
    "date": 5,
}

# ─────────────────────────────────────────
# Core Functions
# ─────────────────────────────────────────

def purify_llm_output(raw_response: str) -> dict:
    """Safe cleaning for LLM responses (Markdown, broken JSON)"""
    # Remove Markdown code fences
    unfenced_response = re.sub(r"^`{3}(?:json)?\s*(.*?)\s*`{3}$", r"\1", raw_response, flags=re.DOTALL | re.IGNORECASE)
    try:
        result = json.loads(unfenced_response)
        if isinstance(result, dict):
            return result
        else:
            logger.error(f"Invalid LLM response format: Not a dictionary.")
            return {}
    except json.JSONDecodeError as e:
        # Fallback for broken JSON
        logger.error(f"JSON Parse Error: {e}")
        return {}

def enforce_pii_schema(pii: dict) -> dict:
    """Enforce PII schema"""
    # Create a new dictionary with only the expected keys,
    # Defaulting to empty lists if a key is missing or not a list using dictionary comprehension
    result = {}
    for k in EXPECTED_PII_KEYS:
        val = pii.get(k)
        if isinstance(val, list):
            result[k] = val
        elif isinstance(val, str):
            result[k] = [val]
        else:
            result[k] = []
    return result

def build_replacement_list(text: str, pii: dict) -> ReplacementMetadata:
    """
    Create a list of replacements from PII.
    Output from this function is stored in DB to track changes.
    """
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    raw_entries: list[dict[str, Any]] = []
    
    # Search for exact matches of tokens in the original text
    for category, tokens in pii.items():
        pii_type = CATEGORY_TYPE_MAP.get(category, category)
        
        # Safeguard: Use set to avoid redundant searches when LLM outputs the same word multiple times
        for token in set(tokens):
            if not token or not isinstance(token, str):
                continue
            
            # Use re.escape to neutralize special characters and find all matches in the text
            for match in re.finditer(re.escape(token), text):
                raw_entries.append({
                    "id": str(uuid.uuid4().hex[:8]),
                    "type": pii_type,
                    "start": match.start(),
                    "length": len(token),
                    "method": "auto"
                })

    # Sort by start position (same start position, prioritize longer span)
    raw_entries.sort(key=lambda e: (e["start"], -e["length"]))

    # Merge overlapping/contained spans greedily
    merged_replacements: list[ReplacementEntry] = []
    for entry in raw_entries:
        if not merged_replacements:
            merged_replacements.append(entry)
        else:
            last = merged_replacements[-1]
            last_end = last["start"] + last["length"]
            entry_end = entry["start"] + entry["length"]
            # Overlapping detected
            if entry["start"] < last_end:
                # Extend the end position of the last entry if the current entry extends further
                last["length"] = max(entry_end, last_end) - last["start"]
                # Apply priorities (the smaller the number, the higher the priority)
                last_priority = TYPE_PRIORITY.get(last["type"], 99)
                entry_priority = TYPE_PRIORITY.get(entry["type"], 99)
                if entry_priority < last_priority:
                    last["type"] = entry["type"]
            else:
                merged_replacements.append(entry)

    result = {
        "text_hash": text_hash,
        "status": "Unconfirmed",
        "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds').replace("+00:00", "Z"),
        "replacements": merged_replacements
    }
    # logger.info(f"Result: {result}")
    return result

def mask_pii(text: str, metadata: ReplacementMetadata) -> str:
    """
    Mask PII in the text using ReplacementMetadata.
    """
    # Hash check to prevent major accidents if the caller forgets to check
    current_hash = hashlib.sha256(text.encode()).hexdigest()
    if current_hash != metadata["text_hash"]:
        raise ValueError("Text hash mismatch. Invalid replacement metadata for this raw text.")
    masked_text = list(text)
    for entry in sorted(metadata["replacements"], key=lambda e: e["start"], reverse=True):
        start = entry["start"]
        length = entry["length"]
        masked_text[start:start+length] = ["[MASKED]"]
    return "".join(masked_text)