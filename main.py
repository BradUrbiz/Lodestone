import os
from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory

load_dotenv()
app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html", key=os.getenv("CARTO_API_KEY", ""))

@app.route("/imgs/<path:filename>")
def images(filename):
    return send_from_directory(os.path.join(app.root_path, "imgs"), filename)
<<<<<<< HEAD
=======
@app.route("/api/route", methods=["POST"])
def get_route():
# getting current GPS and target GPS
    data = request.get_json()
    start_lat = data["start_lat"]
    start_lon = data["start_lon"]
    dest_lat = data["dest_lat"]
    dest_lon = data["dest_lon"]

    # use foot path from Open Source Routing Machine (OSRM)
    url = f"https://router.project-osrm.org/route/v1/foot/{start_lon},{start_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
    res = requests.get(url).json()

    route = res["routes"][0]
    
    # coords for route
    path_points = []
    for coord in route["geometry"]["coordinates"]:
        path_points.append([coord[1], coord[0]])

    # safety scoring factors
    route_factors = {
        "sidewalk": True,
        "crosswalk": True,
        "school_zone": True,
        "no_sidewalk": False,
        "highway": False,
        "high_speed": False,
        "pedestrian_crash": False
    }

    safety_score = calculate_score(route_factors)

    return jsonify({
        "points": path_points,
        "minutes": round(route["duration"] / 60),
        "miles": round(route["distance"] * 0.000621371, 2),
        "score": safety_score
    })
>>>>>>> c0b4163 (Add routing path via OSRM foot, color correction for distinctness)

if __name__ == "__main__":
    app.run(debug=True)