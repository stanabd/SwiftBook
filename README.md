# SwiftBook

A monetized travel search engine — flights, hotels, and car rentals. Earn affiliate commissions on every booking. Powered by Travelpayouts API with smart mock-data fallback.

## Revenue Streams

| Source | Provider | Commission | How |
|---|---|---|---|
| Flights | Aviasales via Travelpayouts | 1-1.5% of ticket price | User clicks "Book" → redirected via your affiliate link |
| Hotels | Booking.com via Travelpayouts | 4-5% of booking value | User clicks "Book" → redirected with your marker |
| Car Rentals | DiscoverCars via Travelpayouts | 5-8% of rental value | User clicks "Book" → redirected with your marker |
| Display Ads | Google AdSense (optional) | CPC/CPM | 3 ad slots built into the page |

All revenue is tracked in the built-in Revenue Dashboard at `/Revenue` in the nav.

---

## Quick Start

### macOS / Linux
```bash
chmod +x start.sh
./start.sh
```

### Windows
Double-click `start.bat`

### Manual
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open **http://localhost:8000**

---

## Setup Guide (Start Earning)

### Step 1: Sign up for Travelpayouts (free, ~2 minutes)

1. Go to [travelpayouts.com](https://www.travelpayouts.com) and create a free account
2. Once logged in, go to **Programs** and join:
   - **Aviasales** (flights — auto-approved)
   - **Hotellook / Booking.com** (hotels)
   - **DiscoverCars** (car rentals)
3. Find your **API Token** under developer settings
4. Find your **Marker** (affiliate ID) in your account settings

### Step 2: Configure your environment

```bash
cp .env.example .env
```

Edit `.env`:
```
TRAVELPAYOUTS_TOKEN=your_token_here
TRAVELPAYOUTS_MARKER=your_marker_here
```

### Step 3: Start the server

```bash
./start.sh
```

You'll see in the terminal:
```
SwiftBook ready — API: Travelpayouts connected | Affiliate: ACTIVE (earning commissions!)
```

### Step 4 (Optional): Add Google AdSense

1. Sign up at [adsense.google.com](https://adsense.google.com)
2. Get your publisher ID (e.g., `ca-pub-1234567890123456`)
3. Add it to `.env`:
```
ADSENSE_PUB_ID=ca-pub-1234567890123456
```
4. Restart the server — the 3 ad slots (leaderboard, in-feed, footer) will auto-activate

---

## Project Structure

```
SwiftBook/
├── index.html          ← Frontend SPA (with affiliate links + ad slots)
├── main.py             ← FastAPI backend (Travelpayouts API + click tracking)
├── requirements.txt    ← Python dependencies
├── .env.example        ← Environment template (READ THIS FIRST)
├── start.sh            ← Quick-start (macOS/Linux)
├── start.bat           ← Quick-start (Windows)
└── swiftbook.db        ← SQLite database (auto-created)
```

---

## API Reference

| Endpoint | Description |
|---|---|
| `GET /api/search/flights` | Search flights (params: `from`, `to`, `date`, `passengers`) |
| `GET /api/search/hotels` | Search hotels (params: `city`, `checkIn`, `checkOut`, `guests`) |
| `GET /api/search/cars` | Search car rentals (params: `location`, `pickUp`, `dropOff`) |
| `GET /api/deals` | Today's best deals with affiliate links |
| `POST /api/track/click` | Track an affiliate link click |
| `GET /api/analytics/clicks` | Revenue dashboard data (click counts, breakdowns) |
| `GET /api/config/monetization` | Current monetization status + setup checklist |
| `GET /api/health` | Server health + data source + affiliate status |
| `GET /docs` | Interactive Swagger API docs |

---

## How Monetization Works

### Affiliate Flow
```
User searches → Sees results → Clicks "Book"
    ↓
Click tracked in SQLite (type, params, URL, timestamp)
    ↓
User redirected to provider site (Aviasales / Booking.com / DiscoverCars)
via YOUR affiliate link (contains your marker)
    ↓
User completes booking on provider site
    ↓
You earn commission (paid monthly by Travelpayouts)
```

### Revenue Dashboard
Built into the site at the bottom. Shows:
- Total clicks by type (flights, hotels, cars)
- Recent click activity
- Commission rate reference
- Setup checklist (API token, marker, AdSense status)

### Ad Slots
Three pre-built ad placements:
1. **Leaderboard** (728x90) — between hero and results
2. **In-feed** (728x90) — after search results
3. **Footer banner** (728x90) — after "How it Works" section

These auto-activate when you add your `ADSENSE_PUB_ID`. Without it, they show placeholder boxes.

---

## Travelpayouts API Coverage

| Feature | API Used | Access |
|---|---|---|
| Flight prices | Aviasales Data API (`/aviasales/v3/prices_for_dates`) | Free with token |
| Hotel lookup | Hotellook Lookup API (`/api/v2/lookup.json`) | Free with token |
| Hotel prices | Hotellook Widget Data (`widget_location_dump.json`) | Free with token |
| Autocomplete | Travelpayouts Autocomplete API | Free |
| Click tracking | Built-in SQLite | Local |

### Data Flow

1. Check SQLite cache (10-minute TTL)
2. If miss → call Travelpayouts API
3. If API fails or not configured → use mock data with affiliate links
4. Cache result and return

The app never breaks — it degrades gracefully.

---

## Deploy to Production

### Railway (easiest)
1. Push to GitHub
2. Go to [railway.app](https://railway.app) → Deploy from GitHub
3. Add env variables in dashboard
4. Done — public URL instantly

### Render
1. Push to GitHub
2. Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Add env variables

### VPS
```bash
TRAVELPAYOUTS_TOKEN=xxx TRAVELPAYOUTS_MARKER=xxx uvicorn main:app --host 0.0.0.0 --port 80
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla JS, Tailwind CSS CDN, Plus Jakarta Sans + Instrument Serif |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Database | SQLite (cache + click tracking) |
| Data API | Travelpayouts (Aviasales + Hotellook) |
| Affiliate | Travelpayouts partner network |
| Ads | Google AdSense (optional) |
| HTTP | httpx (async) |

---

SwiftBook &copy; 2026
