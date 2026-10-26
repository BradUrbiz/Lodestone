import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
hackclub_ai_key = os.getenv("HACKCLUB_AI_KEY", "")

# scoring parameters
parameters = {
    # infrastructure additions
    "sidewalk": 50,
    "crosswalk": 50,
    "school_zone": 75,
    # infrastructure demerits
    "no_sidewalk": -75,
    "no_crosswalk": -75,
    "highway": -100,
    # crash deductions from maryland 2025 open data
    "recent_pedestrian_crash": -120,
    "recent_car_crash": -60,
    # ai risk deductions
    "high_speed": -65,
    "pedestrian_crash": -100,
    "car_crash": -75,
    # community reported hazard deduction
    "community_hazard": -80
}

# community hazards check
def get_community_hazard_factors(coords):
    hazards_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hazards.json")
    if not os.path.exists(hazards_file):
        return {"community_hazard": False}

    try:
        with open(hazards_file, "r") as f:
            hazards = json.load(f)
    except Exception:
        return {"community_hazard": False}

    for h in hazards:
        h_lat = h.get("lat")
        h_lon = h.get("lon")
        for pt in coords:
            if abs(pt[0] - h_lat) < 0.0004 and abs(pt[1] - h_lon) < 0.0004:
                return {"community_hazard": True}

    return {"community_hazard": False}

# maryland 2025 state crash data
def get_real_crash_data(coords):
    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    south, north = min(lats) - 0.001, max(lats) + 0.001
    west, east = min(lons) - 0.001, max(lons) + 0.001

    url = (
        f"https://opendata.maryland.gov/resource/ubvg-82ak.json?"
        f"$where=crash_date between '2025-01-01T00:00:00' and '2025-12-31T23:59:59' "
        f"AND latitude between {south} and {north} "
        f"AND longitude between {west} and {east}"
        f"&$limit=20"
    )

    has_ped_crash = False
    has_car_crash = False

    try:
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            crashes = res.json()
            if len(crashes) > 0:
                has_car_crash = True
                for c in crashes:
                    if c.get("harm_event_desc", "").lower() in ["pedestrian", "bicycle", "pedalcycle"]:
                        has_ped_crash = True
                        break
            print(f"[Real 2025 Crash Data]: Car Crashes={has_car_crash}, Ped Crashes={has_ped_crash}")
    except Exception:
        pass

    return {
        "recent_pedestrian_crash": has_ped_crash,
        "recent_car_crash": has_car_crash
    }

# overpass osm infrastructure
def get_osrm_infrastructure_score(coords):
    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    south, north = min(lats) - 0.001, max(lats) + 0.001
    west, east = min(lons) - 0.001, max(lons) + 0.001

    query = f"""
    [out:json][timeout:5];
    (
        node["highway"="crossing"]({south},{west},{north},{east});
        way["highway"="footway"]({south},{west},{north},{east});
        way["sidewalk"]({south},{west},{north},{east});
        way["highway"~"motorway|trunk|primary"]({south},{west},{north},{east});
        node["amenity"="school"]({south},{west},{north},{east});
    );
    out tags;
    """

    elements = []
    mirrors = [
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass-api.de/api/interpreter"
    ]
    headers = {"User-Agent": "LodestoneApp/1.0"}

    for m in mirrors:
        try:
            res = requests.post(m, data={"data": query}, headers=headers, timeout=3)
            if res.status_code == 200 and "json" in res.headers.get("Content-Type", ""):
                elements = res.json().get("elements", [])
                break
        except Exception:
            continue

    has_crosswalk = any(el.get("tags", {}).get("highway") == "crossing" for el in elements)
    has_sidewalk = any("sidewalk" in el.get("tags", {}) or el.get("tags", {}).get("highway") == "footway" for el in elements)
    has_highway = any(el.get("tags", {}).get("highway") in ["motorway", "trunk"] for el in elements)
    has_school = any(el.get("tags", {}).get("amenity") == "school" for el in elements)

    return {
        "sidewalk": has_sidewalk,
        "no_sidewalk": not has_sidewalk,
        "crosswalk": has_crosswalk,
        "no_crosswalk": not has_crosswalk,
        "school_zone": has_school,
        "highway": has_highway
    }

# gemini risk auditor
def get_ai_risk_factors(street_names, distance_mi, minutes):
    if not hackclub_ai_key:
        return {"high_speed": False, "pedestrian_crash": False, "car_crash": False}

    prompt = (
        f"You are a pedestrian safety auditor. Safety is your NUMBER ONE priority ALWAYS.\n"
        f"Streets: {', '.join(street_names) if street_names else 'Residential walk paths'}\n"
        f"Distance: {distance_mi} mi, Time: {minutes} min.\n\n"
        f"Determine:\n"
        f"1. high_speed: (true if speed limit over 35 mph or multi-lane arterial, else false)\n"
        f"2. pedestrian_crash: (true if high-risk crossings or dangerous turns, else false)\n"
        f"3. car_crash: (true if heavy vehicle traffic corridor, else false)\n"
        f"Return ONLY raw JSON: {{\"high_speed\": false, \"pedestrian_crash\": false, \"car_crash\": false}}"
    )

    try:
        res = requests.post(
            "https://ai.hackclub.com/proxy/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {hackclub_ai_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-3.5-flash-lite",
                "messages": [
                    {"role": "system", "content": "Return raw JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 60,
                "temperature": 0.0
            },
            timeout=5
        ).json()

        text = res["choices"][0]["message"].get("content", "").strip()
        clean = text.replace("```json", "").replace("```", "").strip()
        s = clean.find("{")
        e = clean.rfind("}")
        if s != -1 and e != -1:
            data = json.loads(clean[s:e+1])
            print(f"[AI Success for {street_names[:2]}]: {data}")
            return data
        return {"high_speed": False, "pedestrian_crash": False, "car_crash": False}
    except Exception:
        return {"high_speed": False, "pedestrian_crash": False, "car_crash": False}

# composite score evaluation
def evaluate_route(coords, street_names, distance_mi, minutes, cached_osm=None, cached_crashes=None):
    osm_factors = cached_osm if cached_osm else get_osrm_infrastructure_score(coords)
    crash_factors = cached_crashes if cached_crashes else get_real_crash_data(coords)
    ai_factors = get_ai_risk_factors(street_names, distance_mi, minutes)
    community_factors = get_community_hazard_factors(coords)

    all_factors = {**osm_factors, **crash_factors, **ai_factors, **community_factors}

    score = 1000
    for factor, is_present in all_factors.items():
        if is_present and factor in parameters:
            score += parameters[factor]

    # road crossing penalty
    crossings = max(0, len(street_names) - 1)
    penalty = crossings * 35
    score -= penalty

    # distance penalty
    score -= int(distance_mi * 30)

    score = max(50, min(score, 1000))
    print(f"Final Score: {score} (Crossings: {crossings}, Penalty: -{penalty})")
    return score, all_factors, osm_factors, crash_factors