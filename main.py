import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_from_directory
import requests
from services.scoring import evaluate_route

load_dotenv()
app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html", key=os.getenv("CARTO_API_KEY", ""))

@app.route("/imgs/<path:filename>")
def images(filename):
    return send_from_directory(os.path.join(app.root_path, "imgs"), filename)

# query osrm helper
def query_osrm(start_lon, start_lat, dest_lon, dest_lat, via_lon=None, via_lat=None):
    if via_lon and via_lat:
        pts = f"{start_lon},{start_lat};{via_lon},{via_lat};{dest_lon},{dest_lat}"
    else:
        pts = f"{start_lon},{start_lat};{dest_lon},{dest_lat}"

    url = f"https://router.project-osrm.org/route/v1/foot/{pts}?overview=full&geometries=geojson&alternatives=3&steps=true"
    try:
        return requests.get(url, timeout=6).json().get("routes", [])
    except Exception:
        return []

@app.route("/api/route", methods=["POST"])
def get_route():
    # current and target GPS
    data = request.get_json()
    start_lat = float(data["start_lat"])
    start_lon = float(data["start_lon"])
    dest_lat = float(data["dest_lat"])
    dest_lon = float(data["dest_lon"])

    # osrm natural walking routes
    raw_routes = query_osrm(start_lon, start_lat, dest_lon, dest_lat)

    # if osrm only gives 1 option
    if len(raw_routes) < 3:
        mid_lat = (start_lat + dest_lat) / 2
        mid_lon = (start_lon + dest_lon) / 2
        d_lat = dest_lat - start_lat
        d_lon = dest_lon - start_lon

        # 20% offset to branch onto nearby parallel corridors
        alt1 = query_osrm(start_lon, start_lat, dest_lon, dest_lat, mid_lon + (d_lat * 0.20), mid_lat - (d_lon * 0.20))
        alt2 = query_osrm(start_lon, start_lat, dest_lon, dest_lat, mid_lon - (d_lat * 0.20), mid_lat + (d_lon * 0.20))

        if alt1:
            raw_routes.append(alt1[0])
        if alt2:
            raw_routes.append(alt2[0])

    if not raw_routes:
        return jsonify({"error": "No walking route found"}), 404

    base_dist = raw_routes[0]["distance"]
    evaluated_routes = []
    seen_street_sequences = set()
    cached_osm = None
    cached_crashes = None

    for r in raw_routes:
        # prevent loop by discarding routes >30% longer 
        if r["distance"] > base_dist * 1.3:
            continue

        # pull turn steps and streets
        all_steps = []
        unique_streets = []
        for leg in r.get("legs", []):
            for step in leg.get("steps", []):
                name = step.get("name", "").strip()
                if name:
                    all_steps.append(name)
                    if name not in unique_streets:
                        unique_streets.append(name)

        # prevent loop by discarding if it walks down a street, enters a loop, and comes back onto same street
        is_loop = False
        for i in range(len(all_steps) - 2):
            if all_steps[i] == all_steps[i + 2] and all_steps[i] != all_steps[i + 1]:
                is_loop = True
                break
        if is_loop:
            continue

        # prevent identical duplicate routes by checking street sequence and coordinates
        street_sig = "->".join(all_steps)
        pts = [[c[1], c[0]] for c in r["geometry"]["coordinates"]]
        coord_sig = f"{len(pts)}-{round(r['distance'], 1)}"

        if street_sig in seen_street_sequences or coord_sig in seen_street_sequences:
            continue
        seen_street_sequences.add(street_sig)
        seen_street_sequences.add(coord_sig)

        mins = round(r["duration"] / 60)
        mi = round(r["distance"] * 0.000621371, 2)

        score, factors, cached_osm, cached_crashes = evaluate_route(
            pts, unique_streets, mi, mins, cached_osm, cached_crashes
        )

        evaluated_routes.append({
            "points": pts,
            "minutes": mins,
            "miles": mi,
            "score": score,
            "factors": factors
        })

    # if anti-loop filters were too strict, keep at least the direct route
    if not evaluated_routes:
        r = raw_routes[0]
        pts = [[c[1], c[0]] for c in r["geometry"]["coordinates"]]
        evaluated_routes.append({
            "points": pts,
            "minutes": round(r["duration"] / 60),
            "miles": round(r["distance"] * 0.000621371, 2),
            "score": 600,
            "factors": {}
        })

    # sort so highest safety score is primary
    evaluated_routes.sort(key=lambda x: x["score"], reverse=True)

    return jsonify({
        "primary": evaluated_routes[0],
        "alternates": evaluated_routes[1:3]
    })

if __name__ == "__main__":
    app.run(debug=True)