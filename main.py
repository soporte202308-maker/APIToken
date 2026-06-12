import re
import json
import urllib.parse
from datetime import datetime
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from urllib3.exceptions import InsecureRequestWarning

# Desactivar advertencias de SSL inseguro (mantenido de tu script)
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

app = FastAPI(
    title="Netflix NFToken Generator API",
    description="API para generar enlaces NFToken a partir de cookies de Netflix",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fmglobals.com/"],  # <-- Pon aquí tu página web exacta
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN Y CONSTANTES ORIGINALES ---
API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
COOKIE_KEYS = ("NetflixId", "SecureNetflixId", "nfvdid", "OptanonConsent")
REQUIRED_COOKIE = "NetflixId"

QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}

BASE_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.context.ab-tests": "",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.client.iosversion": "15.8.5",
    "accept-language": "en-US;q=1",
    "x-netflix.argo.abtests": "",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Dhaka",
}

# --- MODELOS DE DATOS (Pydantic) ---
class TokenRequest(BaseModel):
    cookie_data: str = Field(
        ..., 
        description="El string de la cookie. Puede ser crudo, formato Netscape o JSON.",
        example="NetflixId=v1_abc123...; SecureNetflixId=v1_xyz..."
    )

class TokenResponse(BaseModel):
    status: str
    login_url: str
    expires_at: str

# --- FUNCIONES DE LOGICA ORIGINAL ---
def parse_netscape_cookie_line(line):
    parts = line.strip().split("\t")
    if len(parts) >= 7:
        return {parts[5]: parts[6]}
    return {}

def _decode_cookie_value(value):
    if isinstance(value, str) and "%" in value:
        try:
            return urllib.parse.unquote(value)
        except Exception:
            return value
    return value

def extract_cookie_dict(text):
    cookie_dict = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        cookie_dict.update(parse_netscape_cookie_line(line))

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, list):
        for cookie in data:
            name = cookie.get("name")
            value = cookie.get("value")
            if name in COOKIE_KEYS and isinstance(value, str):
                cookie_dict[name] = _decode_cookie_value(value)
    elif isinstance(data, dict):
        if any(key in data for key in COOKIE_KEYS):
            for key in COOKIE_KEYS:
                value = data.get(key)
                if isinstance(value, str):
                    cookie_dict[key] = _decode_cookie_value(value)
        elif isinstance(data.get("cookies"), list):
            for cookie in data["cookies"]:
                name = cookie.get("name")
                value = cookie.get("value")
                if name in COOKIE_KEYS and isinstance(value, str):
                    cookie_dict[name] = _decode_cookie_value(value)

    for key in COOKIE_KEYS:
        if key in cookie_dict:
            continue
        match = re.search(rf"(?<!\w){re.escape(key)}=([^;,\s]+)", text)
        if match:
            cookie_dict[key] = _decode_cookie_value(match.group(1))

    return cookie_dict

def format_expiry(expires):
    if not isinstance(expires, (int, float)):
        return "Unknown"
    try:
        return datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(expires)

# --- ENDPOINTS DE LA API ---

@app.post("/generate", response_model=TokenResponse)
def generate_token(payload: TokenRequest):
    # 1. Extraer las cookies usando tu método original
    cookie_dict = extract_cookie_dict(payload.cookie_data)
    
    if not cookie_dict:
        raise HTTPException(status_code=400, detail="No se encontró ninguna cookie válida en el texto enviado.")
    
    netflix_id = cookie_dict.get(REQUIRED_COOKIE)
    if not netflix_id:
        raise HTTPException(status_code=400, detail="Falta la cookie requerida obligatoria: NetflixId")

    # 2. Configurar headers y hacer la petición
    headers = dict(BASE_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"

    try:
        response = requests.get(
            API_URL,
            params=QUERY_PARAMS,
            headers=headers,
            timeout=30,
            verify=False,
        )
        response.raise_for_status()
        
        # 3. Procesar la respuesta de Netflix
        data = response.json()
        token_data = (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default") or {}
        token = token_data.get("token")
        expires = token_data.get("expires")

        if not token:
            raise HTTPException(status_code=400, detail="Netflix no devolvió ningún token. Es posible que la cookie haya expirado.")

        if isinstance(expires, int) and len(str(expires)) == 13:
            expires //= 1000

        # 4. Devolver la respuesta estructurada en JSON
        return TokenResponse(
            status="success",
            login_url="https://netflix.com/?nftoken=" + token,
            expires_at=format_expiry(expires)
        )

    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Error al conectar con los servidores de Netflix: {str(exc)}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(exc)}")
