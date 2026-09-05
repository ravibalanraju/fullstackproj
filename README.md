# Prompt-Based AI Q&A API

A Flask backend that answers education questions using an LLM. Two REST endpoints fetch a prompt template from MongoDB, substitute the user's question into the template, call an AI API, and store every request/response pair for auditing.

Built as a backend case study: single-request API, asynchronous bulk API, MongoDB persistence, and structured error handling.

## AI Provider Note

The assignment calls for the OpenAI/ChatGPT API. This implementation uses the **official OpenAI Python SDK**, but configured against **Groq's OpenAI-compatible endpoint** (`https://api.groq.com/openai/v1`) with the free model `openai/gpt-oss-120b`, because no OpenAI account with credits was available for this project.

The OpenAI SDK treats any compatible `base_url` identically, so this is a configuration choice, not a code change: to run against OpenAI itself, set `OPENAI_API_KEY` to an OpenAI key, remove `OPENAI_BASE_URL` from `.env`, and set `OPENAI_MODEL` (e.g. `gpt-4o-mini`). No code changes are required.

## Tech Stack

- **Python 3.12** with **Flask 3** (`Flask[async]` for native async route handlers)
- **MongoDB Atlas** (PyMongo) — prompt templates and request history
- **OpenAI Python SDK** — LLM calls (sync client for single requests, `AsyncOpenAI` for bulk)
- **python-dotenv** — environment configuration

## API Reference

Base URL: `http://127.0.0.1:5000`

### POST /api/ask — single question

Request body:

```json
{"userInput": "Explain photosynthesis to a 10-year-old"}
```

Response (200):

```json
{"response": "Photosynthesis is how plants make their own food..."}
```

**What happens:** the `Education_Prompt` template is fetched from the `prompts` collection, `{{userinput}}` is replaced with the user's question, the rendered prompt is sent to the LLM, the answer is returned as JSON, and the full exchange is saved to the `history` collection.

### POST /api/ask/bulk — multiple questions, processed asynchronously

Request body:

```json
{"userInput": [
  "What is the capital of France?",
  "Who wrote Romeo and Juliet?",
  "Which planet is known as the Red Planet?"
]}
```

Response (200) — always in **input order**, regardless of which LLM call finishes first:

```json
{"responses": [
  "The capital of France is Paris...",
  "Romeo and Juliet was written by William Shakespeare...",
  "The Red Planet is Mars..."
]}
```

### Error responses

Both endpoints validate input and return structured JSON errors:

| Case | Status | Body |
|------|--------|------|
| Missing / malformed body, wrong type, empty input | 400 | `{"error": "Request body must be JSON with a non-empty 'userInput' string"}` |
| Bulk item that is not a non-empty string | 400 | `{"error": "Every item in 'userInput' must be a non-empty string"}` |
| Bulk request larger than 50 inputs | 400 | `{"error": "Bulk requests are limited to 50 inputs"}` |
| Prompt template missing from database | 404 | `{"error": "Prompt template not found"}` |
| LLM provider failure on `/api/ask` | 502 | `{"error": "AI request failed: <details>"}` |

In bulk requests, a failed LLM call does **not** fail the whole request: each input gets its own result slot, and a failed item returns `{"error": "..."}` in its original position while the other items still return their answers.

## Design Decisions

**Asynchronous bulk processing.** The bulk route is an `async def` handler (Flask's native async support). Each question runs through `asyncio.gather()`, so all LLM calls are in flight concurrently instead of one after another — three questions complete in roughly the time of one. `gather` returns results in argument order by construction, which is how input-order responses are guaranteed even when calls complete out of order.

**Per-item error isolation.** `gather(..., return_exceptions=True)` means one failed LLM call becomes an error slot in the results list rather than aborting the entire batch. History is still saved for every item that succeeded.

**Async client created per request.** The `AsyncOpenAI` client is instantiated inside `process_bulk()` rather than at module level, so it is always bound to the event loop that will actually run the coroutines.

**Non-blocking database writes.** PyMongo is synchronous, so history inserts are dispatched with `asyncio.to_thread()` to keep the event loop free while writes complete.

**Single endpoint stays synchronous.** `/api/ask` handles one question with one LLM call — there is nothing to run concurrently, so a plain sync handler (with the sync client) is the simpler, correct choice.

**Prompt templates in the database.** Prompts live in MongoDB (`prompts` collection) rather than hardcoded, so they can be changed or added without a code deploy. The `history` collection stores the raw input, the *rendered* prompt that was actually sent, the response, and a UTC timestamp — enough to audit exactly what the model saw and returned.

## Database Schema

Database: `case_study`

**`prompts`** — seeded on startup if empty:

```json
{"_id": "Education_Prompt", "template": "You are an expert in education domain. Answer the following: {{userinput}}"}
```

**`history`** — one document per answered question:

```json
{
  "user_input": "What is the capital of France?",
  "prompt": "You are an expert in education domain. Answer the following: What is the capital of France?",
  "response": "The capital of France is Paris...",
  "timestamp": "2026-09-05T05:58:59.230+00:00"
}
```

## Setup

Prerequisites: Python 3.10+ and a MongoDB Atlas cluster (free tier works).

```bash
# 1. Clone and enter the project
git clone <repository-url>
cd FullstackProj

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env         # then edit .env with your keys
# (create a .env based on .env.example with your MongoDB URI and API key)

# 5. Run
python run.py
```

The server starts on `http://127.0.0.1:5000`. The `prompts` collection is seeded automatically on startup if it is empty.

## Testing

With curl:

```bash
# Single question
curl -X POST http://127.0.0.1:5000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"userInput": "Explain photosynthesis to a 10-year-old"}'

# Bulk — three questions concurrently
curl -X POST http://127.0.0.1:5000/api/ask/bulk \
  -H "Content-Type: application/json" \
  -d '{"userInput": ["What is the capital of France?", "Who wrote Romeo and Juliet?", "Which planet is known as the Red Planet?"]}'
```

Or in Postman: `POST` → `http://127.0.0.1:5000/api/ask` → Body → raw → JSON, with the body above. (The `Content-Type: application/json` header matters — Flask 3 will not parse the body as JSON without it.)

Verify persistence in MongoDB Atlas: Database → Browse Collections → `case_study.history` shows one document per answered question, including the rendered prompt and UTC timestamp.

## Project Structure

```
FullstackProj/
├── run.py                # Entry point — starts the dev server
├── requirements.txt      # Pinned dependencies
├── .env.example          # Environment variable template (no real keys)
└── app/
    ├── __init__.py       # Application factory, blueprint registration
    ├── database.py       # MongoDB connection, collections, seeding
    ├── services.py       # Prompt rendering, LLM calls (sync + async), history writes
    └── routes.py         # /api/ask and /api/ask/bulk endpoints, validation
```

## Limitations

- The bulk endpoint caps at 50 inputs per request to bound resource use; it has no request timeout.
- `seed_data()` runs inside the app factory, so a bad `MONGODB_URI` fails fast at startup rather than at first request. For a case study this is intentional; a production deployment would seed out-of-band.
- The development server (`python run.py`) is for local use; use a WSGI server (e.g. gunicorn) in production.
