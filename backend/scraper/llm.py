import os
import random
import asyncio
import httpx
import json
from typing import Optional, List, Dict, Any
import ollama

# --- Configuration ---
GROQ_API_KEYS = [k.strip() for k in os.getenv("GROQ_API_KEY", "").split(",") if k.strip()]
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "minimax-m2:cloud")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

_ollama_semaphore = None
def get_ollama_semaphore():
    global _ollama_semaphore
    if _ollama_semaphore is None:
        _ollama_semaphore = asyncio.Semaphore(4) # Throttles to max 4 concurrent LLM requests to prevent 429
    return _ollama_semaphore

# --- Logging ---
LOG_FILE = "scraper.log"

def log(msg: str):
    from datetime import datetime
    import sys
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - [LLM] {msg}\n")
    print(f"LLM: {msg}", file=sys.stderr)

# --- Groq Client ---
async def summarize_with_groq(text: str) -> Optional[str]:
    """Groq LPU summarization with retry on rate-limit."""
    if not GROQ_API_KEYS or not text or len(text) < 400:
        return None
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "Summarize this news article in 3 bullet points. Max 60 words total."},
            {"role": "user", "content": text[:4000]},
        ],
        "max_tokens": 150,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(3):
            api_key = random.choice(GROQ_API_KEYS)
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            try:
                resp = await client.post(url, headers=headers, json=payload, timeout=15)
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                elif resp.status_code == 429:
                    wait = 2 ** attempt
                    log(f"Groq rate limited. Waiting {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    log(f"Groq API error: {resp.status_code}")
                    break
            except Exception as e:
                log(f"Groq request error: {e}")
                await asyncio.sleep(1)
    return None

# --- Ollama Client ---
async def extract_metadata_with_ollama(body: str) -> Dict[str, Optional[str]]:
    """
    Extract author, agency, and clean the body using local Ollama instance.
    """
    if not body or len(body) < 100:
        return {"author": None, "agency": None, "body": body}

    prompt = f"""
    Analyze the following news article text and extract the 'Author' and the 'Publishing Agency/News Organization'.
    Also, identify if the text is complete or just a "junk" snippet (like a paywall or cookie notice).
    If the text is a valid article, provide a cleaned version of the body by removing ads, social media links, and irrelevant navigation text.
    
    CRITICAL: DO NOT SUMMARIZE the article. Keep the internal content exactly as is, just remove external junk.

    Text:
    \"\"\"{body[:6000]}\"\"\"

    Return ONLY a JSON object with the following keys:
    - "author": (string or null, e.g., "John Doe")
    - "agency": (string or null, e.g., "The New York Times")
    - "is_junk": (boolean, true if the text is mostly bot-detection, paywall, or cookie consent messages)
    - "cleaned_body": (string, the preserved article content without ads/junk. DO NOT SUMMARIZE.)
    """

    try:
        client = ollama.AsyncClient(host=OLLAMA_BASE_URL)
        sem = get_ollama_semaphore()
        
        response = None
        for attempt in range(4):
            try:
                async with sem:
                    response = await client.chat(model=OLLAMA_MODEL, messages=[
                        {'role': 'user', 'content': prompt},
                    ], format='json')
                break
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "too many concurrent" in err_str) and attempt < 3:
                    log(f"Ollama rate limit hit (429). Retrying in {2 ** attempt}s...")
                    await asyncio.sleep(2 ** attempt + random.uniform(0, 1))
                else:
                    raise e
                    
        content = response['message']['content']
        log(f"Raw Ollama Meta: {content[:100]}...")
        
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback: find json block in text
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    # Final fallback logic: regex parse
                    data = {}
                    auth_m = re.search(r'"author"\s*:\s*(?:null|"([^"]*)")', content, re.IGNORECASE)
                    data["author"] = auth_m.group(1) if auth_m and auth_m.group(1) else None
                    agency_m = re.search(r'"agency"\s*:\s*(?:null|"([^"]*)")', content, re.IGNORECASE)
                    data["agency"] = agency_m.group(1) if agency_m and agency_m.group(1) else None
                    junk_m = re.search(r'"is_junk"\s*:\s*(true|false)', content, re.IGNORECASE)
                    data["is_junk"] = True if (junk_m and junk_m.group(1).lower() == 'true') else False
            else:
                raise ValueError("No JSON found in response")

        return {
            "author": data.get("author"),
            "agency": data.get("agency"),
            "is_junk": data.get("is_junk", False),
            "cleaned_body": data.get("cleaned_body", body)
        }
    except Exception as e:
        log(f"Ollama Extraction error: {e}")
        return {"author": None, "agency": None, "body": body, "error": str(e)}

async def verify_agency_with_ollama(body: str, detected_agency: str) -> str:
    """
    Verify if the detected agency is correct based on the text.
    """
    prompt = f"""
    The following article was flagged as being from '{detected_agency}'. 
    Based on the article text below, confirm the actual publishing agency. 
    If it's different, return the correct one. If '{detected_agency}' is correct, return it.

    Text snippet:
    \"\"\"{body[:2000]}\"\"\"

    Return ONLY the agency name as a short string (e.g., "The New York Times"). 
    Do not explain or add commentary. If you cannot identify one, return '{detected_agency}'.
    """
    try:
        client = ollama.AsyncClient(host=OLLAMA_BASE_URL)
        sem = get_ollama_semaphore()
        
        response = None
        for attempt in range(4):
            try:
                async with sem:
                    response = await client.chat(model=OLLAMA_MODEL, messages=[
                        {'role': 'user', 'content': prompt},
                    ])
                break
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "too many concurrent" in err_str) and attempt < 3:
                    await asyncio.sleep(2 ** attempt + random.uniform(0, 1))
                else:
                    raise e
                    
        return response['message']['content'].strip()
    except Exception as e:
        log(f"Ollama agency verify error: {e}")
        return detected_agency

async def check_relevancy_with_ollama(body: str, subject: str) -> Dict[str, Any]:
    """
    Evaluate if the article body is primarily about the given subject (company/brand).
    Used for 'Smart' search mode.
    """
    if not body or len(body) < 150:
        return {"relevant": False, "reason": "Body too short"}

    prompt = f"""
    Evaluate if the following news article is PRIMARILY about the subject '{subject}'.
    
    A relevant article:
    - Mentions '{subject}' in a central role (e.g., product launch, earnings, news about the company).
    - Is not just a passing mention in a list.
    - Is not a gibberish or garbage scraper output.

    Text:
    \"\"\"{body[:4000]}\"\"\"

    Return ONLY a JSON object:
    - "relevant": (boolean)
    - "score": (integer 0-100, where 100 is highly relevant)
    - "reason": (string, 10-word explanation)
    """
    try:
        client = ollama.AsyncClient(host=OLLAMA_BASE_URL)
        sem = get_ollama_semaphore()
        
        response = None
        for attempt in range(4):
            try:
                async with sem:
                    response = await client.chat(model=OLLAMA_MODEL, messages=[
                        {'role': 'user', 'content': prompt},
                    ], format='json')
                break
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "too many concurrent" in err_str) and attempt < 3:
                    await asyncio.sleep(2 ** attempt + random.uniform(0, 1))
                else:
                    raise e
                    
        content = response['message']['content']
        log(f"Raw Ollama Relevancy: {content[:100]}...")
        
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
            else:
                raise ValueError("No JSON found in response")
                
        return {
            "relevant": data.get("relevant", False),
            "score": data.get("score", 0),
            "reason": data.get("reason", "No reason provided")
        }
    except Exception as e:
        log(f"Ollama relevancy error: {e}")
        return {"relevant": True, "score": 50, "reason": "Ollama error, defaulting to relevant"}
