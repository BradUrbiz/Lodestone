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

if __name__ == "__main__":
    app.run(debug=True)