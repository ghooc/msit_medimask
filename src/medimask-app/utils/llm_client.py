import os
import json
import logging
import re
import time
from openai import OpenAI

from pii_core import enforce_pii_schema, purify_llm_output

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────
SYSTEM_PROMPT = """\
You are an expert at extracting Personally Identifiable Information (PII) from Japanese medical text.
Carefully scan the text from beginning to end. Do not miss any items in the middle of the text.

Extract all instances of:
1. names: 氏名 (Pay special attention to names followed by さん, 氏, 君, ちゃん, 様, etc.)
2. locations: 地名 (都道府県, 市区町村, 丁目, 番地, 号室, 交差点, 通り, ビル, 会社, 駅, 空港, 会館, タワー, etc.)
3. hospitals: 施設名 (病院, クリニック, 診療所, センター, 特別養護老人ホーム, 研究所, 治療院, ホスピス, etc.)
4. identifiers: 識別子 (患者ID, 検査ID, カルテ番号, 電話番号, メールアドレス, etc.)
5. dates: 絶対的な年月日や年齢 (2026年11月16日, 昭和45年, 平成13年, 8月3日, 76歳, 19840502, etc.)

Examples of information not considered PII:
1. Relative time and date information: 相対的な年月日 (本日, 3年前, 妊娠14週, etc.)

Output STRICTLY a JSON object with the following keys. Do not output anything else.
{
  "names": [],
  "locations": [],
  "hospitals": [],
  "identifiers": [],
  "dates": []
}
"""


# Environment variables for Ollama
llm_base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
llm_model = os.getenv("LLM_MODEL", "qwen")
llm_api_key = os.getenv("LLM_API_KEY", "ollama")
llm_temperature = 0.0


# OpenAI client with Ollama integration
client = OpenAI(base_url=llm_base_url, api_key=llm_api_key)

def extract_pii_with_retry(text: str, max_retries: int = 3, retry_delay: int = 1, client: OpenAI = client, model: str = llm_model) -> dict:
    """Extract PII with retry logic"""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=llm_temperature,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
            )
            raw_pii = response.choices[0].message.content
            # logger.info(f"Raw PII: {raw_pii}") # TODO: For debug
            purified_pii = purify_llm_output(raw_pii)
            formatted_pii = enforce_pii_schema(purified_pii)
            return formatted_pii
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to extract PII after {max_retries} attempts: {e}")
                return enforce_pii_schema({})
            time.sleep(retry_delay)