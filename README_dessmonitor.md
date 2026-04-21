# Dessmonitor → Ubuntu → Zabbix → Grafana
### Integración de Inversor Solar con Wi-Fi Plug Pro vía API Dessmonitor

---

> **Desarrollado por:** Analista de Sistema II  Manuel Moya
> **Empresa:** TECNOVEN SERVICES C.A. Y VEIMESP C.A.
> **Departamento:** Soporte Técnico — Maracay, 2025
> **Contacto:** Soportearagua@tecnovenca.net | +58 (424) 358-5386 / (416) 543-8925

---

## 🗺️ Arquitectura

```
[Wi-Fi Plug Pro Q0029218780531]  —  Nodo Palo Negro
      |  sube datos automáticamente vía Wi-Fi
[Dessmonitor Cloud — web.dessmonitor.com]
      |  HTTPS — API pública — cada 5 minutos
[Ubuntu Server — IP Pública]
  |-- /opt/dessmonitor/api_dessmonitor.py   (FastAPI — puerto 8000)
  |-- /opt/dessmonitor/.env                 (credenciales protegidas)
      |  HTTP local 127.0.0.1:8000
[Zabbix Server — Host: DESSMONITOR]
  |-- Item maestro: HTTP_AGENT cada 5 min
  |-- 19 Items DEPENDENT con JSONPath
  |-- 7 Triggers de alerta
      |
[Grafana] ✅
```

> El datalogger ya sube los datos solo a Dessmonitor.
> No se necesita VPN ni configurar el router remoto.

---

## 📋 Datos del Dispositivo

| Parámetro    | Valor                    |
|--------------|--------------------------|
| Dispositivo  | Wi-Fi Plug Pro           |
| PN           | Q0029218780531           |
| SN           | Q002921878053109E901     |
| Devcode      | 2537                     |
| Devaddr      | 1                        |
| Company Key  | bnrl_frRFjEz8Mkn         |
| Plataforma   | SmartESS / Dessmonitor   |
| Nodo         | Palo Negro               |

---

## 📁 Archivos del Proyecto

| Archivo                        | Ubicación en servidor                         |
|--------------------------------|-----------------------------------------------|
| `api_dessmonitor.py`           | `/opt/dessmonitor/api_dessmonitor.py`         |
| `env_dessmonitor.txt`          | `/opt/dessmonitor/.env`  (renombrar)          |
| `dessmonitor-api.service`      | `/etc/systemd/system/dessmonitor-api.service` |
| `zbx_export_dessmonitor.yaml`  | Importar en Zabbix → Configuration → Hosts   |

> ⚠️ El archivo `.env` NO debe subirse a GitHub. Está incluido en `.gitignore`.

---

## ⚡ Instalación Paso a Paso

### UBUNTU — Paso 1: Instalar dependencias
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip -y
pip3 install fastapi uvicorn requests python-dotenv --break-system-packages
sudo pip3 install fastapi uvicorn requests python-dotenv --break-system-packages
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
uvicorn --version
```

### UBUNTU — Paso 2: Crear directorio y copiar archivos
```bash
sudo mkdir -p /opt/dessmonitor
sudo chown $USER:$USER /opt/dessmonitor
# Copiar api_dessmonitor.py y .env al directorio
```

### UBUNTU — Paso 3: Configurar credenciales en .env
```bash
nano /opt/dessmonitor/.env
# Completar con usuario, contraseña y company-key reales
sudo chmod 600 /opt/dessmonitor/.env
sudo chown root:root /opt/dessmonitor/.env
```

### UBUNTU — Paso 4: Instalar servicio systemd
```bash
sudo cp dessmonitor-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dessmonitor-api
sudo systemctl start dessmonitor-api
sudo systemctl status dessmonitor-api
```

### UBUNTU — Paso 5: Verificar el API
```bash
curl http://localhost:8000/dessmonitor/lastdata | python3 -m json.tool
curl http://localhost:8000/dessmonitor/status
curl http://localhost:8000/dessmonitor/raw | python3 -m json.tool
```

### ZABBIX — Paso 6: Importar y configurar
1. **Configuration → Hosts → Import** → seleccionar `zbx_export_dessmonitor.yaml`
2. Abrir host **DESSMONITOR** → **Interfaces** → IP: `127.0.0.1` → **Update**
3. Verificar en **Monitoring → Latest data → Host: DESSMONITOR**

---

## 📊 Items en Zabbix

| Key                               | Unidad | Descripción                  |
|-----------------------------------|--------|------------------------------|
| `dessmonitor.bat.voltage`         | V      | Voltaje batería               |
| `dessmonitor.bat.soc`             | %      | SOC batería                   |
| `dessmonitor.bat.current`         | A      | Corriente carga batería       |
| `dessmonitor.grid.voltage`        | V      | Voltaje red eléctrica         |
| `dessmonitor.grid.current`        | A      | Corriente red                 |
| `dessmonitor.grid.freq`           | Hz     | Frecuencia red                |
| `dessmonitor.pv.voltage`          | V      | Voltaje panel solar           |
| `dessmonitor.pv.current`          | A      | Corriente panel solar         |
| `dessmonitor.pv.power`            | W      | Potencia panel solar          |
| `dessmonitor.load.current`        | A      | Corriente de carga            |
| `dessmonitor.load.power`          | VA     | Potencia aparente carga       |
| `dessmonitor.load.percent`        | %      | Porcentaje de carga           |
| `dessmonitor.sys.output.voltage`  | V      | Voltaje salida inversor       |
| `dessmonitor.sys.output.freq`     | Hz     | Frecuencia salida             |
| `dessmonitor.sys.bus.voltage`     | V      | Voltaje bus DC                |
| `dessmonitor.sys.pv.current`      | A      | Corriente PV sistema          |
| `dessmonitor.sys.mains.current`   | A      | Corriente red sistema         |
| `dessmonitor.sys.inv.current`     | A      | Corriente inversor            |
| `dessmonitor.timestamp`           | Texto  | Timestamp último dato         |

---

## 🔔 Triggers

| Trigger                      | Severidad | Condición          |
|------------------------------|-----------|--------------------|
| Batería baja                 | WARNING   | SOC < 20%          |
| Batería crítica              | HIGH      | SOC < 10%          |
| Sin generación solar         | WARNING   | PV = 0W            |
| Voltaje de red bajo          | HIGH      | Grid < 100V        |
| Carga alta del inversor      | WARNING   | Load > 80%         |
| Carga crítica del inversor   | HIGH      | Load > 95%         |
| Sin datos del inversor       | HIGH      | Sin datos > 15 min |

---

## 🔧 Comandos de mantenimiento

```bash
sudo systemctl status dessmonitor-api
sudo systemctl restart dessmonitor-api
sudo tail -f /var/log/dessmonitor.log
sudo journalctl -u dessmonitor-api -n 50 --no-pager
curl http://localhost:8000/dessmonitor/lastdata | python3 -m json.tool
```

---

## 🚨 Solución de Problemas

| Problema                            | Solución                                                           |
|-------------------------------------|--------------------------------------------------------------------|
| status=1/FAILURE                    | `cd /opt/dessmonitor && sudo python3 api_dessmonitor.py`          |
| ERR_MISSING_PARAMETER               | Verificar `company-key` en `.env` (obtener de F12 → authSource)  |
| Arrays vacíos pars:{}               | Verificar SN exacto: `Q002921878053109E901`                       |
| Campos con valor 0                  | `curl localhost:8000/dessmonitor/raw` ver nombres de par          |
| Zabbix unexpected tag "triggers"    | Triggers deben ir a nivel raíz en Zabbix 7.0 (ya corregido)      |
| Zabbix unknown function "hour"      | Función eliminada en Zabbix 7.0 (ya corregido en YAML)           |
| address already in use port 8000    | `sudo systemctl stop dessmonitor-api && systemctl start ...`      |

---

## 🔒 Seguridad y GitHub

```bash
# Proteger credenciales en el servidor
sudo chmod 600 /opt/dessmonitor/.env
sudo chown root:root /opt/dessmonitor/.env

# En GitHub: NUNCA subir .env
# El .gitignore ya lo excluye automáticamente
```

### Qué subir a GitHub ✅
```
api_dessmonitor.py
dessmonitor-api.service
zbx_export_dessmonitor.yaml
README_dessmonitor.md
.gitignore
```

### Qué NO subir a GitHub ❌
```
.env                  ← contiene contraseñas
env_dessmonitor.txt   ← contiene contraseñas
```

---

## 🐙 GitHub — Primeros pasos

```bash
git init
git add api_dessmonitor.py dessmonitor-api.service zbx_export_dessmonitor.yaml README_dessmonitor.md .gitignore
git commit -m "Integración Dessmonitor → Zabbix — by Analista de Sistema II Manuel Moya"
git remote add origin https://github.com/TU_USUARIO/dessmonitor-zabbix.git
git push -u origin main
```

---

*© 2025 TECNOVEN SERVICES C.A. Y VEIMESP C.A.*
*Desarrollado por: Analista de Sistema II  Manuel Moya*
