#!/usr/bin/env python3
"""
================================================================================
  API Middleware — Dessmonitor → Zabbix
  ─────────────────────────────────────────────────────────────────────────────
  Empresa    : TECNOVEN SERVICES C.A. Y VEIMESP C.A.
  Desarrollado por: Analista de Sistema II  Manuel Moya
  Departamento: Soporte Técnico — Maracay, 2025
  ─────────────────────────────────────────────────────────────────────────────
  Dispositivo: Wi-Fi Plug Pro Q0029218780531
  Nodo       : Palo Negro
  Plataforma : SmartESS / Dessmonitor (devcode 2537)
  Versión    : 1.0.0
  ─────────────────────────────────────────────────────────────────────────────
  Descripción:
    Middleware FastAPI que se autentica contra la API pública de Dessmonitor,
    consulta los datos en tiempo real del inversor y los expone como JSON plano
    en el puerto 8000 para que Zabbix los consuma vía HTTP_AGENT cada 5 minutos.

  Endpoints:
    GET /                          → Info del API
    GET /dessmonitor/lastdata      → Datos del inversor (usado por Zabbix)
    GET /dessmonitor/raw           → Arrays crudos para debug
    GET /dessmonitor/status        → Estado de conexión con Dessmonitor

  Instalación:
    pip3 install fastapi uvicorn requests python-dotenv --break-system-packages
    sudo pip3 install fastapi uvicorn requests python-dotenv --break-system-packages

  Ejecución manual:
    cd /opt/dessmonitor
    uvicorn api_dessmonitor:app --host 0.0.0.0 --port 8000

  Como servicio:
    sudo systemctl start dessmonitor-api
  ─────────────────────────────────────────────────────────────────────────────
  © 2025 TECNOVEN SERVICES C.A. Y VEIMESP C.A.
  Desarrollado por: Analista de Sistema II  Manuel Moya
================================================================================
"""

import hashlib
import os
import time
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# ── Cargar credenciales desde /opt/dessmonitor/.env ──────────────────────────
load_dotenv("/opt/dessmonitor/.env")

app = FastAPI(
    title="Dessmonitor Middleware — Nodo Palo Negro",
    version="1.0.0",
    description=(
        "Middleware desarrollado por Analista de Sistema II Manuel Moya | "
        "TECNOVEN SERVICES C.A. Y VEIMESP C.A."
    )
)

# ==============================================================================
# CONFIGURACIÓN — leída desde .env (nunca hardcodeada aquí)
# ==============================================================================
DESS_USER        = os.getenv("DESS_USER",        "")
DESS_PASSWORD    = os.getenv("DESS_PASSWORD",    "")
DESS_PN          = os.getenv("DESS_PN",          "Q0029218780531")
DESS_SN          = os.getenv("DESS_SN",          "Q002921878053109E901")
DESS_DEVCODE     = os.getenv("DESS_DEVCODE",     "2537")
DESS_DEVADDR     = os.getenv("DESS_DEVADDR",     "1")
DESS_COMPANY_KEY = os.getenv("DESS_COMPANY_KEY", "")
DESS_BASE_URL    = "https://web.dessmonitor.com/public/"
DESS_SOURCE      = "1"
DESS_I18N        = "en_US"

# ==============================================================================
# CACHÉ DEL TOKEN — se renueva automáticamente cada hora
# ==============================================================================
_token_cache = {
    "token":      None,
    "secret":     None,
    "expires_at": 0
}

# ==============================================================================
# FUNCIONES AUXILIARES
# ==============================================================================

def sha1(text: str) -> str:
    """Genera hash SHA1 requerido por la API de Dessmonitor."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def generate_salt() -> str:
    """Salt = timestamp en milisegundos."""
    return str(int(time.time() * 1000))


# ==============================================================================
# AUTENTICACIÓN
# ==============================================================================

def authenticate() -> dict:
    """
    Autentica contra Dessmonitor y retorna token + secret.
    El token se cachea 1 hora para no re-autenticar en cada llamada.
    Parámetros requeridos descubiertos vía análisis de red (F12):
      - usr, source, company-key
    La firma se genera como: SHA1(salt + SHA1(password) + params)
    """
    global _token_cache

    # Retornar token cacheado si aún es válido
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache

    salt          = generate_salt()
    password_hash = sha1(DESS_PASSWORD)
    params        = (f"&action=authSource"
                     f"&usr={DESS_USER}"
                     f"&source={DESS_SOURCE}"
                     f"&company-key={DESS_COMPANY_KEY}")
    sign          = sha1(salt + password_hash + params)
    url           = f"{DESS_BASE_URL}?sign={sign}&salt={salt}{params}"

    resp = requests.get(url, timeout=15)
    data = resp.json()

    if data.get("err") != 0:
        raise Exception(
            f"[AUTH ERROR] {data.get('desc', 'desconocido')} — "
            f"Verifica usuario/contraseña en .env"
        )

    _token_cache["token"]      = data["dat"]["token"]
    _token_cache["secret"]     = data["dat"]["secret"]
    _token_cache["expires_at"] = time.time() + 3600

    print(f"[AUTH] Token renovado correctamente — expira en 1 hora")
    return _token_cache


# ==============================================================================
# CONSULTA DE DATOS — querySPDeviceLastData
# ==============================================================================

def get_device_last_data() -> dict:
    """
    Consulta los últimos datos del inversor en Dessmonitor.

    Grupos de parámetros retornados por la API (devcode 2537):
      pv_ → Panel solar fotovoltaico
      bt_ → Batería
      gd_ → Red eléctrica (Grid/Mains)
      sy_ → Sistema/Inversor
      bc_ → Carga (Load)

    Retorna JSON plano para fácil extracción con JSONPath en Zabbix:
      $.bat_voltage, $.bat_soc, $.grid_voltage, etc.
    """
    auth   = authenticate()
    token  = auth["token"]
    secret = auth["secret"]
    salt   = generate_salt()

    params = (f"&action=querySPDeviceLastData"
              f"&source={DESS_SOURCE}"
              f"&pn={DESS_PN}"
              f"&devcode={DESS_DEVCODE}"
              f"&devaddr={DESS_DEVADDR}"
              f"&sn={DESS_SN}"
              f"&i18n={DESS_I18N}")

    # Firma para consulta de datos: SHA1(salt + secret + token + params)
    sign = sha1(salt + secret + token + params)
    url  = f"{DESS_BASE_URL}?sign={sign}&salt={salt}&token={token}{params}"

    resp = requests.get(url, timeout=15)
    raw  = resp.json()

    if raw.get("err") != 0:
        raise Exception(f"[DATA ERROR] {raw.get('desc', 'desconocido')}")

    pars = raw["dat"]["pars"]
    gts  = raw["dat"].get("gts", "N/A")

    # ── Extraer grupos de parámetros ─────────────────────────────────────────
    pv_list = pars.get("pv_", [])   # Panel solar
    bt_list = pars.get("bt_", [])   # Batería
    gd_list = pars.get("gd_", [])   # Red eléctrica
    sy_list = pars.get("sy_", [])   # Sistema/Inversor
    bc_list = pars.get("bc_", [])   # Carga

    # ── Funciones de extracción ───────────────────────────────────────────────
    def get_float(group: list, *keywords) -> float:
        """Busca un valor numérico por palabra clave en el campo 'par'."""
        for kw in keywords:
            for item in group:
                if kw.lower() in item.get("par", "").lower():
                    try:
                        return float(item["val"])
                    except (ValueError, TypeError):
                        return 0.0
        return 0.0

    def get_str(group: list, *keywords) -> str:
        """Busca un valor texto por palabra clave en el campo 'par'."""
        for kw in keywords:
            for item in group:
                if kw.lower() in item.get("par", "").lower():
                    return str(item.get("val", "N/A"))
        return "N/A"

    # ── Mapeo de parámetros (nombres exactos verificados via F12) ─────────────
    result = {

        # ── Batería ───────────────────────────────────────────────────────────
        # par: "BatVolt"    → Voltaje de batería (V)
        # par: "BatSoc"     → Estado de carga (%)
        # par: "ChargeCurr" → Corriente de carga (A)
        "bat_voltage":         get_float(bt_list, "BatVolt"),
        "bat_soc":             get_float(bt_list, "BatSoc"),
        "bat_current":         get_float(bt_list, "ChargeCurr"),
        "bat_charge_power":    get_float(bt_list, "ChargeCurr"),
        "bat_discharge_power": get_float(bt_list, "ChargeCurr"),

        # ── Red eléctrica (Grid / Mains) ──────────────────────────────────────
        # par: "Mains voltage" → Voltaje de red (V)
        # par: "Grid current"  → Corriente de red (A)
        # par: "GridFreq"      → Frecuencia de red (Hz)
        "grid_voltage":        get_float(gd_list, "Mains voltage"),
        "grid_current":        get_float(gd_list, "Grid current"),
        "grid_freq":           get_float(gd_list, "GridFreq"),

        # ── Panel Solar (PV) ──────────────────────────────────────────────────
        # par: "PvInputVolt"       → Voltaje de entrada PV (V)
        # par: "PvInputCurr"       → Corriente de entrada PV (A)
        # par: "PV charging power" → Potencia de carga PV (W)
        "pv_voltage":          get_float(pv_list, "PvInputVolt"),
        "pv_current":          get_float(pv_list, "PvInputCurr"),
        "pv_power":            get_float(pv_list, "PV charging power"),

        # ── Carga (Load) ──────────────────────────────────────────────────────
        # par: "Load current"        → Corriente de carga (A)
        # par: "Load apparent power" → Potencia aparente (VA)
        # par: "Load rate"           → Porcentaje de carga (%)
        "load_current":        get_float(bc_list, "Load current"),
        "load_power":          get_float(bc_list, "Load apparent power"),
        "load_percent":        get_float(bc_list, "Load rate"),

        # ── Sistema / Inversor ────────────────────────────────────────────────
        # par: "OutVolt"       → Voltaje de salida (V)
        # par: "OutFreq"       → Frecuencia de salida (Hz)
        # par: "BusVolt"       → Voltaje bus DC (V)
        # par: "PvCurr"        → Corriente PV del sistema (A)
        # par: "Mains Current" → Corriente de red del sistema (A)
        # par: "InvCurr"       → Corriente del inversor (A)
        "output_voltage":      get_float(sy_list, "OutVolt"),
        "output_freq":         get_float(sy_list, "OutFreq"),
        "bus_voltage":         get_float(sy_list, "BusVolt"),
        "pv_current_sys":      get_float(sy_list, "PvCurr"),
        "mains_current":       get_float(sy_list, "Mains Current"),
        "inv_current":         get_float(sy_list, "InvCurr"),

        # ── Metadata ──────────────────────────────────────────────────────────
        "timestamp":           gts,
        "pn":                  DESS_PN,
        "sn":                  DESS_SN,
        "devcode":             DESS_DEVCODE,

        # ── Arrays crudos para debug ──────────────────────────────────────────
        "raw_pv":              pv_list,
        "raw_bt":              bt_list,
        "raw_gd":              gd_list,
        "raw_sy":              sy_list,
        "raw_bc":              bc_list,
    }

    return result


# ==============================================================================
# ENDPOINTS FASTAPI
# ==============================================================================

@app.get("/dessmonitor/lastdata", summary="Datos del inversor para Zabbix")
def lastdata():
    """
    Endpoint principal — Zabbix HTTP_AGENT llama aquí cada 5 minutos.
    Retorna JSON plano. Los items DEPENDENT extraen con JSONPath:
      $.bat_soc / $.grid_voltage / $.pv_power / etc.
    """
    try:
        return JSONResponse(content=get_device_last_data())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dessmonitor/raw", summary="Parámetros crudos del inversor (debug)")
def raw_params():
    """
    Muestra los arrays completos con los nombres exactos de 'par'.
    Útil para verificar nombres de parámetros si algún campo retorna 0.
    """
    try:
        data = get_device_last_data()
        return {
            "instruccion": "Usa estos nombres exactos en get_float() si algún campo da 0",
            "pv_params":   data["raw_pv"],
            "bt_params":   data["raw_bt"],
            "gd_params":   data["raw_gd"],
            "sy_params":   data["raw_sy"],
            "bc_params":   data["raw_bc"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dessmonitor/status", summary="Estado de conexión con Dessmonitor")
def status():
    """Verifica que la autenticación con Dessmonitor funciona correctamente."""
    try:
        auth = authenticate()
        return {
            "status":       "ok",
            "token_activo": bool(auth["token"]),
            "dispositivo":  f"PN={DESS_PN} | SN={DESS_SN} | devcode={DESS_DEVCODE}"
        }
    except Exception as e:
        return {"status": "error", "detalle": str(e)}


@app.get("/", summary="Info del API")
def root():
    return {
        "api":          "Dessmonitor Middleware — Nodo Palo Negro",
        "version":      "1.0.0",
        "desarrollado": "Analista de Sistema II  Manuel Moya",
        "empresa":      "TECNOVEN SERVICES C.A. Y VEIMESP C.A.",
        "endpoints": [
            "GET /dessmonitor/lastdata  → datos para Zabbix (HTTP_AGENT)",
            "GET /dessmonitor/raw       → nombres exactos de parámetros (debug)",
            "GET /dessmonitor/status    → verificar conexión con Dessmonitor",
        ]
    }
