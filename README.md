# Skill Decay Alerts (SDA)

An adaptive skill-decay detection and decision agent for professional learners.

## Architecture

- **Backend**: FastAPI + LangGraph + pyBKT + SQLite
- **Frontend**: React + Vite
- **LLM**: Featherless.ai (Mistral-7B)

## Setup

### Backend

1. pip install -r requirements.txt`n2. Copy .env.example to .env and fill in Featherless keys
3. uvicorn backend.main:app --reload`n
### Frontend

1. cd frontend && npm install`n2. 
pm run dev`n
## API Endpoints

- GET /skills — All 10 sub-topics with signal bundles
- POST /cycle — Run decision cycle (Invocation 1)
- POST /answer — Submit quiz answer (Invocation 2)
- POST /advance_time — Move simulated clock
- GET /strength-report — Mastery stats + AI summary
- GET /debug/{user_id}/{skill}/{sub_topic} — Dev inspection

## Environment Variables

FEATHERLESS_KEY_1, FEATHERLESS_KEY_2, FEATHERLESS_KEY_3
