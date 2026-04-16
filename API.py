
import hashlib
import os
import time
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv("/opt/dessmonitor/.env")

app = FastAPI(title="Dessmonitor Middleware — Nodo Palo Negro", version="1.0.0")

DESS_USER     = os.getenv("DESS_USER",    "tecnovensoporte@gmail.com")
DESS_PASSWORD = os.getenv("DESS_PASSWORD","Tecno45637954")
DESS_PN       = os.getenv("DESS_PN",      "Q00292187780531")
DESS_SN       = os.getenv("DESS_SN",      "Q00292187805310E9018")
DESS_DEVCODE  = os.getenv("DESS_DEVCODE", "2537")
DESS_DEVADDR  = os.getenv("DESS_DEVADDR", "1")

DESS_BASE_URL = "https://web.dessmonitor.com/public/"
DESS_SOURCE   = "1"
DESS_I18N     = "en_US"

_token_cache = {
    "token":      None,
    "secret":     None,
    "expires_at": 0
}

def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def generate_salt() -> str:
    return str(int(time.time() * 1000))

def authenticate() -> dict:
    global _token_cache

    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache

    salt          = generate_salt()
    password_hash = sha1(DESS_PASSWORD)
    params        = f"&action=authSource&usr={DESS_USER}&source={DESS_SOURCE}"
    sign          = sha1(salt + password_hash + params)

    url = (
        f"{DESS_BASE_URL}?sign={sign}&salt={salt}"
        f"&action=authSource&usr={DESS_USER}&source={DESS_SOURCE}"
    )

    resp = requests.get(url, timeout=15)
    data = resp.json()

    if data.get("err") != 0:
        raise Exception(f"[AUTH ERROR] {data.get('desc','desconocido')} — "
                        f"Verifica usuario/contraseña en .env")

    _token_cache["token"]      = data["dat"]["token"]
    _token_cache["secret"]     = data["dat"]["secret"]
    _token_cache["expires_at"] = time.time() + 3600

    print(f"[AUTH] Token renovado — expira en 1 hora")
    return _token_cache
#Que funcione amen
def get_device_last_data() -> dict:
    auth   = authenticate()
    token  = auth["token"]
    secret = auth["secret"]
    salt   = generate_salt()

    params = (
        f"&action=querySPDeviceLastData"
        f"&source={DESS_SOURCE}"
        f"&pn={DESS_PN}"
        f"&devcode={DESS_DEVCODE}"
        f"&devaddr={DESS_DEVADDR}"
        f"&sn={DESS_SN}"
        f"&i18n={DESS_I18N}"
    )

    sign = sha1(salt + secret + token + params)
    url  = f"{DESS_BASE_URL}?sign={sign}&salt={salt}&token={token}{params}"

    resp = requests.get(url, timeout=15)
    raw  = resp.json()

    if raw.get("err") != 0:
        raise Exception(f"[DATA ERROR] {raw.get('desc','desconocido')}")

    pars = raw["dat"]["pars"]
    gts  = raw["dat"].get("gts", "N/A")

    pv_list = pars.get("pv_", [])
    bt_list = pars.get("bt_", [])
    gd_list = pars.get("gd_", [])
    sy_list = pars.get("sy_", [])
    by_list = pars.get("by_", [])

    def get_float(group: list, *keywords) -> float:
        for kw in keywords:
            for item in group:
                if kw.lower() in item.get("par", "").lower():
                    try:
                        return float(item["val"])
                    except (ValueError, TypeError):
                        return 0.0
        return 0.0

    def get_str(group: list, *keywords) -> str:
        for kw in keywords:
            for item in group:
                if kw.lower() in item.get("par", "").lower():
                    return str(item.get("val", "N/A"))
        return "N/A"

    result = {
        "bat_voltage":          get_float(bt_list, "BatVolt", "battery voltage", "bat volt"),
        "bat_soc":              get_float(bt_list, "BatSoc",  "battery soc", "soc"),
        "bat_current":          get_float(bt_list, "BatCurr", "battery current", "bat curr"),
        "bat_power":            get_float(bt_list, "BatPower","battery power",   "bat power"),
        "bat_charge_power":     get_float(bt_list, "ChargePower", "charge power"),
        "bat_discharge_power":  get_float(bt_list, "DischargePower", "discharge power"),
        "bat_type":             get_str  (bt_list, "BatTypeSet", "battery type"),

        "grid_voltage":         get_float(gd_list, "Mains voltage", "grid voltage", "vgrid"),
        "grid_current":         get_float(gd_list, "Grid current",  "grid curr",   "igrid"),
        "grid_freq":            get_float(gd_list, "GridFreq",      "grid freq",   "freq"),
        "grid_power":           get_float(gd_list, "grid power",    "mains power"),

        "pv_voltage":           get_float(pv_list, "pv voltage", "vpv",  "pv volt"),
        "pv_current":           get_float(pv_list, "pv current", "ipv",  "pv curr"),
        "pv_power":             get_float(pv_list, "pv power",   "ppv",  "pv watt"),

        "load_power":           get_float(by_list, "load power",   "output power"),
        "load_percent":         get_float(by_list, "load percent", "load pct"),
        "load_voltage":         get_float(by_list, "output volt",  "load volt"),
        "load_current":         get_float(by_list, "output curr",  "load curr"),
        "load_freq":            get_float(by_list, "output freq",  "load freq"),

        "inverter_temp":        get_float(sy_list, "temperature", "temp"),
        "status":               get_str  (sy_list, "Current state", "working mode", "status"),
        "device_status_text":   get_str  (sy_list, "device status", "state of machine"),

        "timestamp":   gts,
        "pn":          DESS_PN,
        "sn":          DESS_SN,
        "devcode":     DESS_DEVCODE,

        "raw_pv":  pv_list,
        "raw_bt":  bt_list,
        "raw_gd":  gd_list,
        "raw_sy":  sy_list,
        "raw_by":  by_list,
    }

    return result

@app.get("/dessmonitor/lastdata")
def lastdata():
    try:
        return JSONResponse(content=get_device_last_data())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dessmonitor/raw")
def raw_params():
    try:
        data = get_device_last_data()
        return {
            "instruccion": "Usa estos nombres exactos en get_float() si algun campo da 0",
            "pv_params":  data["raw_pv"],
            "bt_params":  data["raw_bt"],
            "gd_params":  data["raw_gd"],
            "sy_params":  data["raw_sy"],
            "by_params":  data["raw_by"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dessmonitor/status")
def status():
    try:
        auth = authenticate()
        return {
            "status": "ok",
            "token_activo": bool(auth["token"]),
            "dispositivo": f"PN={DESS_PN} | devcode={DESS_DEVCODE}"
        }
    except Exception as e:
        return {"status": "error", "detalle": str(e)}


@app.get("/")
def root():
    return {
        "api":        "Dessmonitor Middleware — Nodo Palo Negro",
        "version":    "1.0.0",
        "endpoints":  [
            "GET /dessmonitor/lastdata",
            "GET /dessmonitor/raw",
            "GET /dessmonitor/status",
        ]
    }
