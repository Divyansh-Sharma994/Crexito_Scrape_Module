# Specification: Advanced Article Filtering & Metadata Enhancement

## 1. Problem Statement
The current scraping mechanism for brands/companies (e.g., "BCG") results in:
1.  **Low Relevancy:** Articles containing the keyword "BCG" but unrelated to the actual company/brand (gibberish or passing mentions) are saved.
2.  **Missing Metadata:** Essential metadata like "author" and "agency" is frequently missing from scraped articles.
3.  **Duplicates:** The database accumulates duplicate articles for the same story.
4.  **Lack of Flexibility:** Users currently have no way to choose between a "broad keyword search" and a "smart brand search".

## 2. Objectives
Implement a dual-module system to handle search intent and improve data quality:
1.  **Module A: Standard/Broad Search (Current Behavior)**
    *   Scrape all articles containing the exact keyword.
    *   No advanced AI filtering for relevancy.
2.  **Module B: Smart/Brand-Focused Search (Advanced AI filtering)**
    *   Scrape articles.
    *   Apply an LLM/Advanced module to evaluate the article body context.
    *   Only save articles where the brand/company is the *primary subject* or contextually relevant, discarding passive mentions or gibberish.
3.  **Metadata Extraction Enhancement (Both Modules)**
    *   Improve the parsing logic utilizing **Ollama (local LLM)** and **Groq** to reliably extract the `author` and `agency`/`publisher` from the article content.
    *   Ensure "entire data" (cleaned full body) is preserved without junk.
4.  **Deduplication (Both Modules)**
    *   Implement robust deduplication before inserting into the database to prevent duplicate news articles (e.g., deduplicating by exact URL, or similarity hashing on title/body).

## 3. High-Level Requirements
*   **Backend (`/api/scrape` endpoint):** Update the API to accept a `search_mode` parameter (`broad` vs `smart`).
*   **Scraping Engine:**
    *   Implement logic to handle the new `smart` pipeline.
    *   Integrate LLM calls (e.g., via OpenAI or current summarization model) in the `smart` pipeline to assign a "relevancy score" and filter out irrelevant articles.
    *   Strengthen Author/Agency extraction (e.g., using `readability-lxml`, newspaper3k, or LLM-assisted extraction).
*   **Database:** Ensure a strict `UNIQUE` constraint or pre-insertion check on `url` and potentially `title` to enforce deduplication.
*   **Frontend:** Add a user interface toggle/dropdown on the "New Scrape Job" page to select between "Standard Keyword Search" and "Smart Brand Search".
*   **Testing:** Comprehensive unit and integration testing of the new pipeline, specifically testing the relevancy filtering and deduplication.

## 4. Status
**Status: FINALIZED**
