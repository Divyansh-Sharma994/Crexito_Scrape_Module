# ROADMAP: Advanced Article Filtering & Metadata Enhancement

## Phase 1: Deduplication & Database Constraints
**Objective:** Prevent duplicate articles from being saved to the database.
- [ ] Backend: Add `url` uniqueness constraint to `articles` table or implement a robust "upsert" / logical deduplication check before inserting.
- [ ] Backend/Scraper: Ensure the scraper gracefully skips duplicates without failing the entire job.
- [ ] Tests: Add a test verifying duplicate URLs are ignored.

## Phase 2: Core Scraping Enhancements (Author/Agency/Ollama)
**Objective:** Improve raw data extraction for all modes to capture `author` and `agency` using Ollama.
- [x] Backend: Install `ollama` library and update `requirements.txt`.
- [x] Backend: Create central `llm.py` for Ollama and Groq integration.
- [x] Backend/Scraper: Integrate Ollama into `engine.py` and `enrichment.py` for author/agency extraction and body cleaning.
- [ ] Tests: Verify Ollama extraction with `test_llm.py` (requires local Ollama service).

## Phase 3: Smart Search Implementation (LLM Relevancy)
**Objective:** Create the logic for "Smart Brand Search".
- [x] Backend: Update `/api/scrape/` (Job creation endpoint) to accept a `search_mode` parameter (`broad` vs `smart`).
- [x] Backend/Enrichment (`enrichment.py`): Integrate an LLM step for `smart` modes.
  - [x] Create a prompt that analyzes the full body to determine if the keyword/brand is the central topic/relevant or just a passing/gibberish mention.
  - [x] Implement a mechanism to set a record to `status = REJECTED` or skip saving it if irrelevant.
- [x] Tests: Mock LLM tests for positive and negative relevancy scoring (manual verification performed).

## Phase 4: Frontend UI Updates
**Objective:** Expose the new search mode to users.
- [x] Frontend (`pages/NewScrape.jsx`): Add a field (e.g., Radio Buttons: "Standard Keyword Search" vs "Smart Brand Search") inside the New Job form.
- [x] Frontend API: Pass the selected `search_mode` in the job creation payload.

## Phase 5: End-to-End Validation
**Objective:** Final validation before commit.
- [ ] Run backend unit tests.
- [ ] Verify Frontend builds and runs.
- [ ] Perform a live test scrape in `broad` vs `smart` mode.
