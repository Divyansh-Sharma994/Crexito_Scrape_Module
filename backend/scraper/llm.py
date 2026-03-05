import os
import random
import asyncio
import httpx
import json
from typing import Optional, List, Dict, Any
import ollama

# --- Configuration ---
GROQ_API_KEYS = [k.strip() for k in os.getenv("GROQ_API_KEY", "").split(",") if k.strip()]
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

_ollama_semaphore = None
_DETECTED_MODEL = None

async def get_ollama_model() -> str:
    global _DETECTED_MODEL
    if _DETECTED_MODEL:
        return _DETECTED_MODEL
        
    env_model = os.getenv("OLLAMA_MODEL")
    client = ollama.AsyncClient(host=OLLAMA_BASE_URL)
    
    try:
        # Check if any model is currently loaded in memory
        running = await client.ps()
        if running and 'models' in running and len(running['models']) > 0:
            _DETECTED_MODEL = running['models'][0]['name']
            log(f"Detected currently loaded model: {_DETECTED_MODEL}")
            return _DETECTED_MODEL
            
        # Get list of available installed models
        models_info = await client.list()
        if models_info and 'models' in models_info and len(models_info['models']) > 0:
            models = [m['name'] for m in models_info['models']]
            
            # Map environment preference if specified
            if env_model and any(env_model in m for m in models):
                _DETECTED_MODEL = [m for m in models if env_model in m][0]
                log(f"Selected env-specified model: {_DETECTED_MODEL}")
                return _DETECTED_MODEL
                
            # Auto-select fallback preferences based on model families
            for preferred in ["qwen", "llama", "mistral", "gemma"]:
                for m in models:
                    if preferred in m.lower():
                        _DETECTED_MODEL = m
                        log(f"Auto-selected preferred model: {_DETECTED_MODEL}")
                        return _DETECTED_MODEL
                        
            # Return first available if no preference matches
            _DETECTED_MODEL = models[0]
            log(f"Selected first available model: {_DETECTED_MODEL}")
            return _DETECTED_MODEL
    except Exception as e:
        log(f"Failed to auto-detect model, using fallback. Error: {e}")
        
    _DETECTED_MODEL = env_model if env_model else "qwen2.5:3b" # safe fallback
    return _DETECTED_MODEL

def get_ollama_semaphore():
    global _ollama_semaphore
    if _ollama_semaphore is None:
        # Increased to 10 - qwen3:4b is lightweight and can handle more concurrency
        _ollama_semaphore = asyncio.Semaphore(10) 
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
from urllib.parse import urlparse

def get_domain_name(url: str) -> str:
    """Extract a clean domain name from a URL."""
    try:
        domain = urlparse(url).netloc
        if domain.startswith("www."):
            domain = domain[4:]
        # Remove TLD for a cleaner 'Agency' name if needed, or keep it.
        # Let's keep it but capitalized for common ones.
        parts = domain.split('.')
        if len(parts) > 1:
            return parts[-2].capitalize()
        return domain.capitalize()
    except:
        return ""

async def extract_metadata_with_ollama(body: str, url: str = "", context_agency: str = "") -> Dict[str, Optional[str]]:
    """
    Extract author, agency, and clean the body using local Ollama instance.
    Uses URL and context_agency for better accuracy.
    """
    if not body or len(body) < 10:
        return {"author": None, "agency": None, "body": body}

    domain = get_domain_name(url) if url else ""
    context_str = f"Source Info: URL={url}, Domain={domain}, Suggested Agency={context_agency}"

    prompt = f"""
    Analyze the following news article text and extract the 'Author' (person) and the 'Publishing Agency' (news organization).
    
    GUIDELINES:
    - For 'Author': Look for "By [Name]", "Author: [Name]", "By [Name] [Agency]", or prominent person names at the start or end of the article.
    - For 'Agency': If not explicitly named, use the provided 'Domain' ({domain}) as a default. If multiple organizations are mentioned, identify the one that is the source of this specific article (usually mentioned at the top or in the byline).
    - If the 'Suggested Agency' ({context_agency}) is broad (e.g. Google News), try to find the specific publisher.
    - Set 'is_junk' to true if the content is mostly ads, snippets, or a paywall notice rather than the actual article content.

    Source Info: {context_str}

    Text Snippet (First 2000 chars):
    \"\"\"{body[:2000]}\"\"\"

    Return ONLY a JSON object:
    {{
      "author": (string or null),
      "agency": (string or null),
      "is_junk": (boolean)
    }}
    """

    start_time = asyncio.get_event_loop().time()
    try:
        client = ollama.AsyncClient(host=OLLAMA_BASE_URL)
        sem = get_ollama_semaphore()
        
        response = None
        current_model = await get_ollama_model()
        for attempt in range(4):
            try:
                async with sem:
                    response = await client.chat(model=current_model, messages=[
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
                    
        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        log(f"Ollama Meta Extraction took {duration:.2f}s")
                    
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

        # --- Post-processing Smart Fallbacks ---
        res_author = data.get("author")
        res_agency = data.get("agency")
        
        # If agency is null or generic, use domain as strongest fallback
        generic_list = ["google news", "bing news", "msn", "yahoo news", "google", "rss", "feed"]
        if not res_agency or any(g in res_agency.lower() for g in generic_list):
            if domain:
                res_agency = domain
            elif context_agency and not any(g in context_agency.lower() for g in generic_list):
                res_agency = context_agency

        return {
            "author": res_author,
            "agency": res_agency,
            "is_junk": data.get("is_junk", False)
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
    start_time = asyncio.get_event_loop().time()
    try:
        client = ollama.AsyncClient(host=OLLAMA_BASE_URL)
        sem = get_ollama_semaphore()
        
        response = None
        current_model = await get_ollama_model()
        for attempt in range(4):
            try:
                async with sem:
                    response = await client.chat(model=current_model, messages=[
                        {'role': 'user', 'content': prompt},
                    ])
                break
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "too many concurrent" in err_str) and attempt < 3:
                    await asyncio.sleep(2 ** attempt + random.uniform(0, 1))
                else:
                    raise e
                    
        end_time = asyncio.get_event_loop().time()
        log(f"Ollama Agency Verify took {end_time - start_time:.2f}s")
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
    start_time = asyncio.get_event_loop().time()
    try:
        client = ollama.AsyncClient(host=OLLAMA_BASE_URL)
        sem = get_ollama_semaphore()
        
        response = None
        current_model = await get_ollama_model()
        for attempt in range(4):
            try:
                async with sem:
                    response = await client.chat(model=current_model, messages=[
                        {'role': 'user', 'content': prompt},
                    ], format='json')
                break
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "too many concurrent" in err_str) and attempt < 3:
                    await asyncio.sleep(2 ** attempt + random.uniform(0, 1))
                else:
                    raise e
                    
        end_time = asyncio.get_event_loop().time()
        content = response['message']['content']
        log(f"Ollama Relevancy took {end_time - start_time:.2f}s | Raw: {content[:100]}...")
        
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
