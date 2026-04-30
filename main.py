#!/usr/bin/env python3
"""
SwiftBook — FastAPI Backend
Real travel data via Travelpayouts (Aviasales + Hotellook) APIs.
Monetized through affiliate links — every "Book" click earns commission.

Revenue streams:
  1. Flights — Aviasales/Travelpayouts affiliate (1-1.5% of ticket price)
  2. Hotels  — Booking.com via Travelpayouts (4-5% of booking value)
  3. Cars    — DiscoverCars affiliate via Travelpayouts (5-8% commission)
  4. Ad slots (optional) — Google AdSense or Ezoic placements
"""

import os, random, sqlite3, hashlib, json, time
from datetime import date, timedelta, datetime
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlencode, quote_plus

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "swiftbook.db"

# Travelpayouts credentials (sign up free: travelpayouts.com)
TP_TOKEN  = os.getenv("TRAVELPAYOUTS_TOKEN", "")  # API token
TP_MARKER = os.getenv("TRAVELPAYOUTS_MARKER", "")  # Affiliate marker (your ID)

# Affiliate deep-link base URLs (these carry your marker for commission)
AVIASALES_BASE  = "https://www.aviasales.com"      # Flights
HOTELLOOK_BASE  = "https://search.hotellook.com"    # Hotels (Booking.com, etc.)
DISCOVERCARS_BASE = "https://www.discovercars.com"  # Car rentals

# Optional: Google AdSense publisher ID
ADSENSE_PUB_ID = os.getenv("ADSENSE_PUB_ID", "")

# ── Travelpayouts API base URLs ───────────────────────────────────────────────
TP_FLIGHTS_API = "https://api.travelpayouts.com"
TP_HOTELS_API  = "https://engine.hotellook.com/api/v2"
TP_AUTOCOMPLETE = "https://autocomplete.travelpayouts.com"

# ── IATA code helper ──────────────────────────────────────────────────────────
CITY_TO_IATA = {
    "new york": "NYC", "nyc": "NYC", "jfk": "JFK", "lga": "LGA", "ewr": "EWR",
    "los angeles": "LAX", "la": "LAX", "san francisco": "SFO", "sf": "SFO",
    "chicago": "ORD", "miami": "MIA", "orlando": "MCO", "dallas": "DFW",
    "houston": "IAH", "atlanta": "ATL", "boston": "BOS", "seattle": "SEA",
    "denver": "DEN", "las vegas": "LAS", "phoenix": "PHX", "washington": "DCA",
    "dc": "DCA", "philadelphia": "PHL", "san diego": "SAN", "austin": "AUS",
    "nashville": "BNA", "portland": "PDX", "minneapolis": "MSP", "detroit": "DTW",
    "london": "LON", "paris": "PAR", "tokyo": "TYO", "rome": "ROM",
    "barcelona": "BCN", "amsterdam": "AMS", "berlin": "BER", "dubai": "DXB",
    "singapore": "SIN", "sydney": "SYD", "cancun": "CUN", "toronto": "YTO",
    "mexico city": "MEX", "lisbon": "LIS", "madrid": "MAD", "munich": "MUC",
    "hong kong": "HKG", "bangkok": "BKK", "istanbul": "IST", "cairo": "CAI",
    "honolulu": "HNL", "anchorage": "ANC", "salt lake city": "SLC",
    "charlotte": "CLT", "tampa": "TPA", "raleigh": "RDU", "moscow": "MOW",
    "st petersburg": "LED", "phuket": "HKT", "bali": "DPS",
}

AIRLINE_NAMES = {
    "AA": "American Airlines", "DL": "Delta Air Lines", "UA": "United Airlines",
    "WN": "Southwest Airlines", "B6": "JetBlue", "NK": "Spirit Airlines",
    "AS": "Alaska Airlines", "BA": "British Airways", "AF": "Air France",
    "LH": "Lufthansa", "EK": "Emirates", "QR": "Qatar Airways", "SQ": "Singapore Airlines",
    "TK": "Turkish Airlines", "LO": "LOT Polish", "AZ": "ITA Airways",
    "KL": "KLM", "SK": "SAS", "IB": "Iberia", "FR": "Ryanair",
    "U2": "easyJet", "W6": "Wizz Air", "F9": "Frontier", "G4": "Allegiant",
    "SU": "Aeroflot", "CX": "Cathay Pacific", "QF": "Qantas", "NH": "ANA",
    "JL": "Japan Airlines", "AC": "Air Canada", "AM": "Aeromexico",
    "LA": "LATAM", "AV": "Avianca", "HA": "Hawaiian Airlines",
}


def resolve_iata(city: str) -> str:
    """Resolve city name to IATA code."""
    cleaned = city.strip().lower()
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()
    return CITY_TO_IATA.get(cleaned, city.strip()[:3].upper())


def airline_name(code: str) -> str:
    """Get airline name from IATA code."""
    return AIRLINE_NAMES.get(code.upper(), code.upper())


# ── Affiliate link generators (THIS IS HOW YOU MAKE MONEY) ────────────────────

def flight_affiliate_link(origin: str, dest: str, dep_date: str, passengers: int = 1) -> str:
    """
    Generate Aviasales affiliate deep link.
    Commission: 1-1.5% of ticket price on every booking.
    """
    if not TP_MARKER:
        return f"https://www.aviasales.com/search/{origin}{dep_date.replace('-','')}{dest}1?marker=YOUR_MARKER"

    # Aviasales deep link format
    date_fmt = dep_date.replace("-", "")
    return (
        f"{AVIASALES_BASE}/search/{origin}{date_fmt}{dest}{passengers}"
        f"?marker={TP_MARKER}"
    )


def hotel_affiliate_link(city_iata: str, checkin: str, checkout: str, guests: int = 2) -> str:
    """
    Generate Hotellook/Booking.com affiliate deep link.
    Commission: 4-5% of booking value (via Travelpayouts).
    """
    if not TP_MARKER:
        return f"https://search.hotellook.com/?marker=YOUR_MARKER"

    params = {
        "marker": TP_MARKER,
        "locationId": city_iata,
        "checkIn": checkin,
        "checkOut": checkout,
        "adults": guests,
        "currency": "usd",
    }
    return f"{HOTELLOOK_BASE}/?" + urlencode(params)


def hotel_direct_affiliate_link(hotel_id: str, checkin: str, checkout: str) -> str:
    """
    Direct hotel booking link with affiliate marker.
    """
    if not TP_MARKER:
        return f"https://search.hotellook.com/hotel/{hotel_id}?marker=YOUR_MARKER"

    return (
        f"{HOTELLOOK_BASE}/hotel/{hotel_id}"
        f"?marker={TP_MARKER}&checkIn={checkin}&checkOut={checkout}&currency=usd"
    )


def car_affiliate_link(location: str, pickup: str, dropoff: str) -> str:
    """
    Generate DiscoverCars affiliate deep link.
    Commission: 5-8% per booking (via Travelpayouts partner program).
    """
    if not TP_MARKER:
        return f"https://www.discovercars.com/?marker=YOUR_MARKER"

    params = {
        "a_aid": TP_MARKER,
        "pick_up": location,
        "pick_up_date": pickup,
        "drop_off_date": dropoff,
    }
    return f"{DISCOVERCARS_BASE}/?" + urlencode(params)


# ── DB ────────────────────────────────────────────────────────────────────────
def init_db():
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS searches (
            id TEXT PRIMARY KEY, type TEXT, params TEXT,
            results TEXT, created_at REAL DEFAULT (unixepoch())
        );
        CREATE TABLE IF NOT EXISTS deals (
            id TEXT PRIMARY KEY, type TEXT, title TEXT,
            description TEXT, price REAL, original_price REAL,
            discount INTEGER, affiliate_url TEXT,
            active INTEGER DEFAULT 1,
            created_at REAL DEFAULT (unixepoch())
        );
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT, search_params TEXT,
            affiliate_url TEXT, created_at REAL DEFAULT (unixepoch())
        );
    """)
    con.commit()
    con.close()
    logger.info("Database ready (SQLite)")


def cache_get(key: str):
    try:
        con = sqlite3.connect(DB_PATH)
        row = con.execute(
            "SELECT results FROM searches WHERE id=? AND (unixepoch()-created_at)<600",
            (key,),
        ).fetchone()
        con.close()
        return json.loads(row[0]) if row else None
    except:
        return None


def cache_set(key: str, stype: str, params: str, results):
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute(
            "INSERT OR REPLACE INTO searches VALUES(?,?,?,?,unixepoch())",
            (key, stype, params, json.dumps(results)),
        )
        con.commit()
        con.close()
    except:
        pass


def log_click(click_type: str, params: str, url: str):
    """Track affiliate link clicks for analytics/revenue tracking."""
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute(
            "INSERT INTO clicks(type, search_params, affiliate_url) VALUES(?,?,?)",
            (click_type, params, url),
        )
        con.commit()
        con.close()
    except:
        pass


# ── Travelpayouts API: Flights ────────────────────────────────────────────────

async def tp_flight_prices(origin: str, dest: str, dep_date: str) -> Optional[list]:
    """
    Fetch real flight prices from Travelpayouts/Aviasales Data API.
    Endpoint: /aviasales/v3/prices_for_dates
    Returns cached pricing data from recent searches across all booking sites.
    """
    if not TP_TOKEN:
        return None

    import httpx
    origin_code = resolve_iata(origin)
    dest_code = resolve_iata(dest)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{TP_FLIGHTS_API}/aviasales/v3/prices_for_dates",
                params={
                    "origin": origin_code,
                    "destination": dest_code,
                    "departure_at": dep_date,
                    "unique": "false",
                    "sorting": "price",
                    "direct": "false",
                    "cy": "usd",
                    "limit": 15,
                    "page": 1,
                    "one_way": "true",
                    "token": TP_TOKEN,
                },
            )
            if resp.status_code != 200:
                logger.warning(f"Travelpayouts flights returned {resp.status_code}")
                return None

            data = resp.json()
            if not data.get("success") or not data.get("data"):
                return None

            results = []
            for ticket in data["data"]:
                code = ticket.get("airline", "")
                dep_dt = ticket.get("departure_at", "")
                dep_time = dep_dt[11:16] if len(dep_dt) > 15 else "--:--"
                dur_min = ticket.get("duration", 0)
                dur_h = dur_min // 60
                dur_m = dur_min % 60
                stops = ticket.get("transfers", 0)

                # Calculate approximate arrival
                if dep_dt and dur_min:
                    try:
                        from datetime import datetime as dt2
                        dep_obj = dt2.fromisoformat(dep_dt.replace("Z", "+00:00"))
                        arr_obj = dep_obj + timedelta(minutes=dur_min)
                        arr_time = arr_obj.strftime("%H:%M")
                    except:
                        arr_time = "--:--"
                else:
                    arr_time = "--:--"

                aff_link = flight_affiliate_link(origin_code, dest_code, dep_date)

                results.append({
                    "id": f"{code}{ticket.get('flight_number', '')}",
                    "airline": airline_name(code),
                    "code": f"{code} {ticket.get('flight_number', '')}",
                    "departure": dep_time,
                    "arrival": arr_time,
                    "from": origin_code,
                    "to": dest_code,
                    "duration": f"{dur_h}h {dur_m:02d}m" if dur_min else None,
                    "stops": stops,
                    "price": int(ticket.get("price", 0)),
                    "badge": "Nonstop" if stops == 0 else None,
                    "discount_pct": None,
                    "class": "Economy",
                    "affiliate_url": aff_link,
                    "source": "travelpayouts",
                })

            return sorted(results, key=lambda x: x["price"]) if results else None
    except Exception as e:
        logger.warning(f"Travelpayouts flight API error: {e}")
        return None


async def tp_hotel_data(city: str, checkin: str, checkout: str) -> Optional[list]:
    """
    Fetch hotel data from Travelpayouts/Hotellook Hotel Data API.
    Uses the cached prices endpoint for hotel pricing.
    """
    if not TP_TOKEN:
        return None

    import httpx
    city_code = resolve_iata(city)

    try:
        # Use the Hotellook hotel prices cached API
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://yasen.hotellook.com/tp/public/available_selections.json",
                params={
                    "id": 12209,  # Default selection (popular hotels)
                    "currency": "usd",
                    "checkIn": checkin,
                    "checkOut": checkout,
                    "marker": TP_MARKER or "none",
                },
            )
            # Try the lookup API for the specific city
            resp2 = await client.get(
                f"https://engine.hotellook.com/api/v2/lookup.json",
                params={
                    "query": city,
                    "lang": "en",
                    "lookFor": "both",
                    "limit": 10,
                    "token": TP_TOKEN,
                },
            )

            hotels_info = []
            if resp2.status_code == 200:
                lookup_data = resp2.json()
                # Get hotel info from lookup results
                for result in lookup_data.get("results", {}).get("hotels", []):
                    hotels_info.append({
                        "id": str(result.get("id", "")),
                        "name": result.get("label", "Hotel"),
                        "locationName": result.get("locationName", city),
                        "fullName": result.get("fullName", ""),
                    })

            # Also try the cache/prices endpoint for the city
            resp3 = await client.get(
                f"https://yasen.hotellook.com/tp/public/widget_location_dump.json",
                params={
                    "currency": "usd",
                    "language": "en",
                    "limit": 10,
                    "id": city_code,
                    "type": "popularity",
                    "token": TP_TOKEN,
                },
            )

            if resp3.status_code == 200:
                price_data = resp3.json()
                results = []
                nights = 1
                try:
                    ci = date.fromisoformat(checkin)
                    co = date.fromisoformat(checkout)
                    nights = max(1, (co - ci).days)
                except:
                    pass

                for hotel in price_data if isinstance(price_data, list) else []:
                    hotel_id = str(hotel.get("hotel_id", hotel.get("id", "")))
                    name = hotel.get("hotel_name", hotel.get("name", "Hotel"))
                    stars = hotel.get("stars", 0)
                    ppn = hotel.get("price_from", hotel.get("priceFrom", 0))
                    rating = hotel.get("rating", 0)

                    aff_link = hotel_direct_affiliate_link(hotel_id, checkin, checkout)

                    results.append({
                        "id": hotel_id,
                        "name": name,
                        "area": hotel.get("city", city),
                        "rating": round(rating / 10, 1) if rating > 10 else rating,
                        "reviews": hotel.get("reviews_count", None),
                        "price": ppn,
                        "pricePerNight": ppn,
                        "total_price": ppn * nights,
                        "nights": nights,
                        "stars": stars,
                        "amenities": [],
                        "badge": None,
                        "discount_pct": None,
                        "affiliate_url": aff_link,
                        "source": "travelpayouts",
                    })
                return sorted(results, key=lambda x: x["price"]) if results else None

            return None
    except Exception as e:
        logger.warning(f"Travelpayouts hotel API error: {e}")
        return None


# ── Mock data (fallback + car rentals) ────────────────────────────────────────
AIRLINES = [
    ("American Airlines", "AA"), ("Delta Air Lines", "DL"),
    ("United Airlines", "UA"), ("Southwest Airlines", "WN"),
    ("JetBlue", "B6"), ("Spirit Airlines", "NK"), ("Alaska Airlines", "AS"),
    ("British Airways", "BA"), ("Air France", "AF"), ("Lufthansa", "LH"),
]

HOTELS_MOCK = {
    "paris": [
        ("Le Marais Boutique", "Le Marais, Paris", 4.8, 1243, ["WiFi", "Breakfast", "Spa"]),
        ("Grand Hotel du Louvre", "1st Arrondissement", 4.6, 892, ["WiFi", "Pool", "Restaurant"]),
        ("Montmartre Inn", "Montmartre, Paris", 4.5, 567, ["WiFi", "Bar", "Parking"]),
        ("Eiffel Suite Hotel", "7th Arrondissement", 4.7, 2100, ["WiFi", "Spa", "Breakfast"]),
        ("Latin Quarter Hostel", "5th Arrondissement", 4.2, 334, ["WiFi", "Lounge"]),
    ],
    "new york": [
        ("The Manhattan Grand", "Midtown, NYC", 4.7, 3421, ["WiFi", "Gym", "Pool"]),
        ("Brooklyn Loft Hotel", "Williamsburg, NYC", 4.5, 1102, ["WiFi", "Rooftop Bar"]),
        ("Times Square Central", "Midtown, NYC", 4.3, 2890, ["WiFi", "Restaurant", "Concierge"]),
        ("Upper West Suites", "Upper West Side", 4.6, 765, ["WiFi", "Kitchen", "Gym"]),
        ("SoHo Boutique Stay", "SoHo, NYC", 4.8, 511, ["WiFi", "Spa", "Bar"]),
    ],
    "miami": [
        ("South Beach Luxe", "South Beach, Miami", 4.7, 1876, ["WiFi", "Pool", "Beach Access"]),
        ("Brickell City Hotel", "Downtown Miami", 4.4, 923, ["WiFi", "Gym", "Restaurant"]),
        ("Coconut Grove Inn", "Coconut Grove", 4.5, 612, ["WiFi", "Pool", "Parking"]),
        ("Wynwood Art Hotel", "Wynwood, Miami", 4.6, 445, ["WiFi", "Bar", "Gallery"]),
        ("Key Biscayne Resort", "Key Biscayne", 4.9, 289, ["WiFi", "Pool", "Spa", "Beach"]),
    ],
    "london": [
        ("The Kensington", "Kensington, London", 4.7, 2341, ["WiFi", "Breakfast", "Gym"]),
        ("Covent Garden Suites", "Covent Garden", 4.5, 1560, ["WiFi", "Bar", "Restaurant"]),
        ("Shoreditch Boutique", "Shoreditch", 4.4, 890, ["WiFi", "Rooftop", "Lounge"]),
        ("Hyde Park Grand", "Mayfair", 4.8, 3200, ["WiFi", "Pool", "Spa", "Breakfast"]),
        ("Camden Town Stay", "Camden", 4.1, 430, ["WiFi", "Parking"]),
    ],
    "tokyo": [
        ("Shinjuku Tower Hotel", "Shinjuku, Tokyo", 4.6, 2800, ["WiFi", "Onsen", "Restaurant"]),
        ("Shibuya Crossing Inn", "Shibuya", 4.5, 1400, ["WiFi", "Bar", "Gym"]),
        ("Asakusa Ryokan", "Asakusa", 4.8, 670, ["WiFi", "Traditional Baths", "Breakfast"]),
        ("Ginza Luxury Suites", "Ginza", 4.9, 1900, ["WiFi", "Spa", "Pool", "Concierge"]),
        ("Akihabara Budget", "Akihabara", 4.0, 350, ["WiFi", "Laundry"]),
    ],
}

CAR_MODELS = [
    ("Toyota Camry", "Midsize", "Automatic", 5),
    ("Honda Civic", "Compact", "Automatic", 5),
    ("Ford Mustang", "Sports", "Automatic", 4),
    ("Chevrolet Suburban", "Full-size SUV", "Automatic", 8),
    ("Tesla Model 3", "Electric", "Automatic", 5),
    ("Jeep Wrangler", "SUV", "Manual", 5),
    ("BMW 3 Series", "Luxury", "Automatic", 5),
    ("Ford F-150", "Truck", "Automatic", 5),
    ("Nissan Altima", "Midsize", "Automatic", 5),
    ("Hyundai Tucson", "Compact SUV", "Automatic", 5),
]

CAR_PROVIDERS = ["Enterprise", "Hertz", "Avis", "Budget", "Alamo", "National", "Dollar", "Thrifty"]

BADGES_FLIGHT = ["Best Price", "Nonstop Deal", "Price Drop", "Staff Pick"]
BADGES_HOTEL = ["Best Value", "Most Popular", "Guest Favorite", "Deal Saver", "Luxury Pick"]
BADGES_CAR = ["Most Popular", "Best Value", "Limited Offer", "Family Pick", "Eco Choice"]


def rnd_seed(*args) -> random.Random:
    h = hashlib.md5("|".join(str(a) for a in args).encode()).hexdigest()
    return random.Random(int(h[:8], 16))


def mock_flights(origin: str, dest: str, dep_date: str, passengers: int):
    rng = rnd_seed(origin, dest, dep_date)
    origin_code = resolve_iata(origin)
    dest_code = resolve_iata(dest)
    results = []
    airlines = rng.sample(AIRLINES, min(6, len(AIRLINES)))
    for i, (al_name, code) in enumerate(airlines):
        dep_h = rng.randint(5, 22)
        dep_m = rng.choice([0, 15, 30, 45])
        dur_h = rng.randint(1, 14)
        dur_m = rng.choice([0, 10, 15, 20, 25, 30, 35, 40, 45, 50])
        arr_h = (dep_h + dur_h + (dep_m + dur_m) // 60) % 24
        arr_m = (dep_m + dur_m) % 60
        stops = rng.choices([0, 1, 2], weights=[60, 30, 10])[0]
        base = rng.randint(89, 1200)
        disc = rng.choice([0, 0, 0, 5, 10, 15, 20]) if i < 2 else 0
        price = round(base * (1 - disc / 100))
        badge = rng.choice(BADGES_FLIGHT) if rng.random() < 0.3 else None
        aff_link = flight_affiliate_link(origin_code, dest_code, dep_date, passengers)
        results.append({
            "id": f"{code}{rng.randint(100, 999)}",
            "airline": al_name,
            "code": f"{code} {rng.randint(100, 999)}",
            "departure": f"{dep_h:02d}:{dep_m:02d}",
            "arrival": f"{arr_h:02d}:{arr_m:02d}",
            "from": origin_code,
            "to": dest_code,
            "duration": f"{dur_h}h {dur_m:02d}m",
            "stops": stops,
            "price": price * passengers,
            "badge": badge,
            "discount_pct": disc if disc > 0 else None,
            "class": "Economy",
            "affiliate_url": aff_link,
            "source": "mock",
        })
    return sorted(results, key=lambda x: x["price"])


def mock_hotels(city: str, checkin: str, checkout: str, guests: int):
    rng = rnd_seed(city, checkin)
    city_key = city.lower().strip()
    city_code = resolve_iata(city)
    hotel_list = HOTELS_MOCK.get(city_key, None)
    if not hotel_list:
        hotel_list = [
            (f"{city.title()} Grand Hotel", "City Center", 4.5, 800, ["WiFi", "Gym"]),
            (f"The {city.title()} Boutique", "Downtown", 4.3, 620, ["WiFi", "Bar"]),
            (f"{city.title()} Inn & Suites", "Airport Area", 4.1, 450, ["WiFi", "Parking"]),
            (f"Premier {city.title()}", "Business District", 4.6, 310, ["WiFi", "Pool", "Spa"]),
            (f"{city.title()} Budget Stay", "Old Town", 3.9, 290, ["WiFi"]),
        ]
    nights = 1
    try:
        ci = date.fromisoformat(checkin) if checkin else date.today()
        co = date.fromisoformat(checkout) if checkout else ci + timedelta(days=3)
        nights = max(1, (co - ci).days)
    except:
        pass
    results = []
    for i, (name, area, base_rating, base_reviews, amenities) in enumerate(hotel_list):
        ppn = rng.randint(69, 650)
        disc = rng.choice([0, 0, 0, 10, 15, 20]) if i < 2 else 0
        price = round(ppn * (1 - disc / 100))
        badge = BADGES_HOTEL[i % len(BADGES_HOTEL)] if rng.random() < 0.5 else None
        aff_link = hotel_affiliate_link(city_code, checkin or "", checkout or "", guests)
        results.append({
            "id": f"h-{city_key[:3]}-{i}",
            "name": name,
            "area": area,
            "rating": round(base_rating + rng.uniform(-0.2, 0.2), 1),
            "reviews": base_reviews + rng.randint(-50, 200),
            "price": price,
            "pricePerNight": price,
            "total_price": price * nights,
            "nights": nights,
            "amenities": amenities,
            "badge": badge,
            "discount_pct": disc if disc > 0 else None,
            "affiliate_url": aff_link,
            "source": "mock",
        })
    return results


def mock_cars(location: str, pickup: str, dropoff: str):
    rng = rnd_seed(location, pickup)
    days = 1
    try:
        pu = date.fromisoformat(pickup) if pickup else date.today()
        dr = date.fromisoformat(dropoff) if dropoff else pu + timedelta(days=3)
        days = max(1, (dr - pu).days)
    except:
        pass
    cars = rng.sample(CAR_MODELS, min(7, len(CAR_MODELS)))
    aff_link = car_affiliate_link(location, pickup or "", dropoff or "")
    results = []
    for i, (name, category, trans, seats) in enumerate(cars):
        ppd = rng.randint(22, 180)
        disc = rng.choice([0, 0, 0, 10, 15]) if i < 2 else 0
        price = round(ppd * (1 - disc / 100))
        badge = rng.choice(BADGES_CAR) if rng.random() < 0.4 else None
        results.append({
            "id": f"c-{i}",
            "name": name,
            "category": category,
            "transmission": trans,
            "seats": seats,
            "provider": rng.choice(CAR_PROVIDERS),
            "price": price,
            "pricePerDay": price,
            "total_price": price * days,
            "days": days,
            "badge": badge,
            "discount_pct": disc if disc > 0 else None,
            "unlimited_miles": rng.random() > 0.3,
            "free_cancellation": rng.random() > 0.4,
            "affiliate_url": aff_link,
            "source": "mock",
        })
    return sorted(results, key=lambda x: x["price"])


# ── Deal seeder ───────────────────────────────────────────────────────────────
STATIC_DEALS = [
    ("flight", "NYC to Miami Weekend", "Economy · Nonstop · Both ways", 89, 149, 40),
    ("hotel", "Paris Boutique — 5 Nights", "Breakfast included · 4-star · City center", 99, 165, 40),
    ("car", "Compact SUV — Las Vegas 7 Days", "Unlimited miles · Free cancellation", 31, 52, 40),
    ("flight", "LAX to Cancun Escape", "Economy · 1 stop · Nonstop return", 129, 219, 41),
    ("hotel", "NYC Times Square Suite", "3 Nights · Rooftop pool · Gym", 149, 249, 40),
    ("car", "Tesla Model 3 — SF 5 Days", "Electric · Automatic · 5 seats", 44, 72, 39),
]


def seed_deals():
    con = sqlite3.connect(DB_PATH)
    existing = con.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
    if existing == 0:
        for t, title, desc, price, orig, disc in STATIC_DEALS:
            did = hashlib.md5(title.encode()).hexdigest()[:12]
            # Generate affiliate URL based on deal type
            if t == "flight":
                aff = flight_affiliate_link("NYC", "MIA", str(date.today()))
            elif t == "hotel":
                aff = hotel_affiliate_link("PAR", str(date.today()), str(date.today() + timedelta(days=5)))
            else:
                aff = car_affiliate_link("Las Vegas", str(date.today()), str(date.today() + timedelta(days=7)))
            con.execute(
                "INSERT OR IGNORE INTO deals VALUES(?,?,?,?,?,?,?,?,1,unixepoch())",
                (did, t, title, desc, price, orig, disc, aff),
            )
        con.commit()
    con.close()


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_deals()
    has_api = bool(TP_TOKEN)
    has_marker = bool(TP_MARKER)
    logger.info(
        f"SwiftBook ready — "
        f"API: {'Travelpayouts connected' if has_api else 'mock data (add TRAVELPAYOUTS_TOKEN)'} | "
        f"Affiliate: {'ACTIVE (earning commissions!)' if has_marker else 'NOT SET (add TRAVELPAYOUTS_MARKER to earn money)'}"
    )
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SwiftBook API",
    version="2.0.0",
    description="Monetized travel search API — flights, hotels, and car rentals with affiliate commissions.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static assets
assets_dir = BASE_DIR / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_frontend():
    html = BASE_DIR / "index.html"
    if html.exists():
        return FileResponse(html, media_type="text/html")
    return JSONResponse({"error": "Frontend not found"}, status_code=404)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "data_source": "travelpayouts" if TP_TOKEN else "mock",
        "affiliate_active": bool(TP_MARKER),
        "adsense_active": bool(ADSENSE_PUB_ID),
    }


@app.get("/api/search/flights")
async def search_flights(
    _from: str = Query(..., alias="from"),
    to: str = Query(...),
    date: Optional[str] = None,
    passengers: int = 1,
):
    dep_date = date or str(__import__('datetime').date.today() + timedelta(days=7))
    ckey = f"flights|{_from}|{to}|{dep_date}|{passengers}"
    if cached := cache_get(ckey):
        return cached

    # Try Travelpayouts first
    if TP_TOKEN:
        try:
            results = await tp_flight_prices(_from, to, dep_date)
            if results:
                cache_set(ckey, "flights", ckey, results)
                return results
        except Exception as e:
            logger.warning(f"Travelpayouts flights error: {e}")

    # Fallback to mock
    results = mock_flights(_from, to, dep_date, passengers)
    cache_set(ckey, "flights", ckey, results)
    return results


@app.get("/api/search/hotels")
async def search_hotels(
    city: str = Query(...),
    checkIn: Optional[str] = None,
    checkOut: Optional[str] = None,
    guests: int = 2,
):
    ci = checkIn or str(date.today() + timedelta(days=7))
    co = checkOut or str(date.today() + timedelta(days=14))
    ckey = f"hotels|{city}|{ci}|{co}"
    if cached := cache_get(ckey):
        return cached

    # Try Travelpayouts first
    if TP_TOKEN:
        try:
            results = await tp_hotel_data(city, ci, co)
            if results:
                cache_set(ckey, "hotels", ckey, results)
                return results
        except Exception as e:
            logger.warning(f"Travelpayouts hotels error: {e}")

    # Fallback to mock
    results = mock_hotels(city, ci, co, guests)
    cache_set(ckey, "hotels", ckey, results)
    return results


@app.get("/api/search/cars")
async def search_cars(
    location: str = Query(...),
    pickUp: Optional[str] = None,
    dropOff: Optional[str] = None,
):
    pu = pickUp or str(date.today() + timedelta(days=7))
    do = dropOff or str(date.today() + timedelta(days=14))
    ckey = f"cars|{location}|{pu}|{do}"
    if cached := cache_get(ckey):
        return cached

    # Car rentals always use mock + affiliate link to DiscoverCars
    results = mock_cars(location, pu, do)
    cache_set(ckey, "cars", ckey, results)
    return results


@app.get("/api/deals")
async def get_deals():
    try:
        con = sqlite3.connect(DB_PATH)
        rows = con.execute(
            "SELECT id,type,title,description,price,original_price,discount,affiliate_url "
            "FROM deals WHERE active=1 ORDER BY discount DESC LIMIT 6"
        ).fetchall()
        con.close()
        return [
            {
                "id": r[0], "type": r[1], "title": r[2], "description": r[3],
                "price": r[4], "original_price": r[5], "discount": r[6],
                "affiliate_url": r[7],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(e)
        return []


@app.post("/api/track/click")
async def track_click(
    type: str = Query(""),
    params: str = Query(""),
    url: str = Query(""),
):
    """Track affiliate link clicks for revenue analytics."""
    log_click(type, params, url)
    return {"status": "tracked"}


@app.get("/api/analytics/clicks")
async def get_click_analytics():
    """Revenue analytics — see how many affiliate clicks you're generating."""
    try:
        con = sqlite3.connect(DB_PATH)
        total = con.execute("SELECT COUNT(*) FROM clicks").fetchone()[0]
        by_type = con.execute(
            "SELECT type, COUNT(*) as cnt FROM clicks GROUP BY type ORDER BY cnt DESC"
        ).fetchall()
        recent = con.execute(
            "SELECT type, search_params, created_at FROM clicks ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        con.close()
        return {
            "total_clicks": total,
            "by_type": [{"type": r[0], "count": r[1]} for r in by_type],
            "recent": [
                {"type": r[0], "params": r[1], "timestamp": r[2]}
                for r in recent
            ],
            "estimated_revenue_note": (
                "Flights: ~1-1.5% of ticket price per booking | "
                "Hotels: ~4-5% of booking value | "
                "Cars: ~5-8% of rental value"
            ),
        }
    except Exception as e:
        logger.error(e)
        return {"total_clicks": 0, "by_type": [], "recent": []}


@app.get("/api/config/monetization")
async def get_monetization_config():
    """Returns current monetization configuration for the frontend."""
    return {
        "affiliate_active": bool(TP_MARKER),
        "adsense_active": bool(ADSENSE_PUB_ID),
        "adsense_pub_id": ADSENSE_PUB_ID if ADSENSE_PUB_ID else None,
        "revenue_streams": {
            "flights": {
                "provider": "Aviasales via Travelpayouts",
                "commission": "1-1.5% of ticket price",
                "active": bool(TP_MARKER),
            },
            "hotels": {
                "provider": "Booking.com via Travelpayouts",
                "commission": "4-5% of booking value",
                "active": bool(TP_MARKER),
            },
            "cars": {
                "provider": "DiscoverCars via Travelpayouts",
                "commission": "5-8% of rental value",
                "active": bool(TP_MARKER),
            },
            "ads": {
                "provider": "Google AdSense",
                "commission": "CPC/CPM",
                "active": bool(ADSENSE_PUB_ID),
            },
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
