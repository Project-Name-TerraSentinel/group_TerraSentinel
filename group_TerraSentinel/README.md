# group_TerraSentinel

## Setup Instructions

### 1. Prerequisites
- Python 3.8 or newer
- Git
- Docker (optional, for containerized runs)

### 2. Install Dependencies
```sh
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the project root with the following (example):
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
CLAUDE_API_KEY=your_claude_api_key
GIS_API_KEY=your_gis_api_key
```
Refer to service documentation for obtaining keys.

### 4. Run the Backend
```sh
python -m backend.app
```
Or use the provided scripts:
```sh
python run_deployment_tests.py
```

### 5. Run Tests
```sh
pytest backend/tests
```

### 6. Docker Usage
Build and run the container:
```sh
docker build -t terrasentinel .
docker run --env-file .env -p 8000:8000 terrasentinel
```

### 7. Deployment
- Vercel: Follow Vercel docs to deploy the frontend/dashboard.
- Supabase: Set up tables and authentication as per Supabase docs.

---
        **Day 0 (Oct 8) – Kickoff & Scope**
Attend Info Session @ 12:00 PM EAT ✅
Lock one pilot region (e.g., Baringo County, Kenya – known for land degradation)
Define two core users:
Grace, smallholder farmer → needs SMS alerts
David, county land officer → needs dashboard for planning

        **Day 1 (Oct 9) – Data Pipeline**
Use Planetary Computer to pull:
NDVI time series (last 6 months)
Bare soil index
Rainfall anomaly
Compute Degradation Risk Score (0–100)
Store in Supabase parcels table

        **Day 2 (Oct 10) – AI Insight Engine**
Prompt Claude.ai:
“Given NDVI=0.18, 40% rainfall deficit, and sandy soil in Baringo, generate ONE practical, low-cost action for a maize farmer. Use local context.”
Output → recommended_action field

        **Day 3 (Oct 11) – Dual Interfaces**
Farmer channel: Mock WhatsApp message:
“Alert! Your field near Kabarnet shows early erosion. Try mulching with crop residue this week.”
Planner dashboard: Bolt.new map showing “High-Risk Zones” with pop-up actions

        **Day 4 (Oct 12) – Integration & Polish**
Connect data → AI → UI(@Musa wil ace here in collab with @Frank)
Add “Report False Alert” button (community feedback loop)
Deploy to Vercel + Supabase

        **Day 5 (Oct 13) – Demo Ready**
Live URL: terrasentinel.dev
GitHub repo with clean code + README
2-min video showing:
Satellite detects change → AI interprets → farmer gets alert → officer plans restoration

        🌍 Real-World Impact Pathway
Pilot: Partner with county agriculture office in Kenya
Scale: Offer API to FAO’s SEPAL or WRI’s Land & Carbon Lab
Sustainability: Monetize via govt/NGO SaaS tier; keep farmer access free
        ✅ Why TerraSentinel Fits Perfectly
Not sci-fi—production-grade
Uses all required tools: Supabase, Claude, GIS APIs, mgx.dev
Solves real gaps.
Client-ready MVP in 5 days
Path to real deployment

