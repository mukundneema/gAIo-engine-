# Earth Intelligence

Chat with Gemini about how places have changed. Gemini calls a Python function that pulls
real **Sentinel-2** imagery and **Dynamic World V1** land-cover from Google Earth Engine, and
the React UI shows the satellite composites, land-cover maps and area statistics.

Forecasting is intentionally **not** implemented yet: the model is told to refuse to invent
future imagery. The next step is to build and validate a real model on this historical data.

```
frontend/   React + TypeScript (Vite)       -> static site on Vercel
api/        Vercel entrypoint (api/index.py)
backend/    FastAPI, Gemini function calling, Earth Engine retrieval
vercel.json build + routing config
```

## One-time Google setup

1. Create/choose a Google Cloud project and enable the **Earth Engine API**.
2. Register the project for Earth Engine (https://code.earthengine.google.com/register).
3. Create a **service account**, give it the *Earth Engine Resource Viewer* role (or Writer),
   and create a JSON key.
4. Register that service account email for Earth Engine if prompted.
5. Get a Gemini API key from Google AI Studio.

## Run locally (Mac)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in GEMINI_API_KEY and EARTHENGINE_PROJECT
earthengine authenticate    # only if you did not set the service-account vars

uvicorn api.index:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173, /api is proxied to port 8000
```

Test the Earth Engine side alone (no Gemini needed):

```bash
curl -X POST localhost:8000/api/imagery -H 'content-type: application/json' \
  -d '{"place":"Mumbai, India","years":[2016,2020,2025]}'
```

`GET /api/health` shows which credentials are configured.

## Deploy to Vercel

1. Push this folder to GitHub and import it in Vercel (root directory = this folder).
2. Under **Settings -> Environment Variables** add:

| Variable | Value |
|---|---|
| `GEMINI_API_KEY` | your Gemini key |
| `GEMINI_MODEL` | e.g. `gemini-2.5-flash` |
| `EARTHENGINE_PROJECT` | Google Cloud project ID |
| `EARTHENGINE_SERVICE_ACCOUNT` | service account email |
| `EARTHENGINE_PRIVATE_KEY` | the full JSON key (one line) or just its `private_key` |

3. Deploy. Visit `/api/health` to confirm the variables are picked up.

Notes
- `vercel.json` sets `maxDuration` to 60 s for the API; a 3-year request typically fits.
  If requests get slower (bigger areas, more years), move retrieval to a separate worker.
- Thumbnail links come directly from Earth Engine and expire after a while, so old chat
  messages may show broken images after a reload. (Persisting images is a good next step.)

## Data notes

- Imagery: `COPERNICUS/S2_HARMONIZED` (Level-1C), cloud-masked yearly median. L1C is used so
  every year back to 2016 is rendered the same way.
- Land cover: `GOOGLE/DYNAMICWORLD/V1`, per-pixel mode of the yearly label.
- Statistics: sampled at 30 m over a square around the place centre (default 15 km half-width).
- Supported years: 2016 to the current year (the current year is partial).
