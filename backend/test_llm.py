import asyncio
import os
import sys
from scraper.llm import extract_metadata_with_ollama, verify_agency_with_ollama, OLLAMA_MODEL

async def test_ollama():
    test_body = """
    By Jane Smith
    Published by TechCrunch
    
    In a stunning turn of events, Apple has announced the launch of its new AI-powered headset, the Vision AI. 
    The device, which features a custom M3 chip, expects to redefine how users interact with augmented reality.
    
    "We are thrilled to bring this technology to the mass market," said Tim Cook.
    
    Click here to subscribe. All rights reserved. JavaScript is required.
    """
    
    print(f"--- Testing Ollama Metadata Extraction (Model: {OLLAMA_MODEL}) ---")
    try:
        res = await extract_metadata_with_ollama(test_body)
        print(f"Author: {res.get('author')}")
        print(f"Agency: {res.get('agency')}")
        print(f"Is Junk: {res.get('is_junk')}")
        print(f"Cleaned Body Snippet: {res.get('cleaned_body')[:100]}...")
    except Exception as e:
        print(f"Extraction failed: {e}")

    print("\n--- Testing Agency Verification ---")
    try:
        agency = await verify_agency_with_ollama(test_body, "Unknown")
        print(f"Verified Agency: {agency}")
    except Exception as e:
        print(f"Verification failed: {e}")

    print("\n--- Testing Relevancy Check ---")
    try:
        from scraper.llm import check_relevancy_with_ollama
        rel = await check_relevancy_with_ollama(test_body, "Apple")
        print(f"Subject 'Apple' - Relevant: {rel.get('relevant')}, Score: {rel.get('score')}")
        
        rel2 = await check_relevancy_with_ollama(test_body, "Agriculture")
        print(f"Subject 'Agriculture' - Relevant: {rel2.get('relevant')}, Score: {rel2.get('score')}")
        
    except Exception as e:
        print(f"Relevancy check failed: {e}")

    print("\n--- Testing Irrelevant Article ---")
    irr_body = "The local bakery is now selling new blueberry muffins. They are delicious and available every morning for 5 dollars."
    try:
        from scraper.llm import check_relevancy_with_ollama
        rel = await check_relevancy_with_ollama(irr_body, "Artificial Intelligence")
        print(f"Muffins vs 'AI' - Relevant: {rel.get('relevant')}")
    except Exception as e:
        print(f"Irr test failed: {e}")

if __name__ == "__main__":
    # Add parent dir to path for imports
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    asyncio.run(test_ollama())
