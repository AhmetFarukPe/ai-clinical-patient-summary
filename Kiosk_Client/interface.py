"""Streamlit patient kiosk integrated with app_fixed.py.

Run: streamlit run interface_fixed.py
"""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import requests
import streamlit as st

st.set_page_config(page_title="Hasta Kabul Kiosku", page_icon="✚", layout="wide", initial_sidebar_state="collapsed")

BASE_DIR = Path(__file__).resolve().parent
SUPPORT_DIR = Path(
    os.environ.get(
        "KIOSK_SUPPORT_DIR",
        str(BASE_DIR.parent / "App_Backend"),
    )
)
API_ENDPOINT = os.environ.get("HASTA_CHECKIN_API_URL", "http://localhost:8000/api/v1/hasta-checkin")
API_KEY = os.environ.get("KIOSK_API_KEY")
CAMERA_SCRIPT = Path(
    os.environ.get(
        "KIOSK_CAMERA_SCRIPT",
        str(SUPPORT_DIR / "kamera_sensor.py"),
    )
)
CAMERA_TIMEOUT_SECONDS = 50

if str(SUPPORT_DIR) not in sys.path:
    sys.path.append(str(SUPPORT_DIR))

try:
    import token_servis
except ImportError:
    token_servis = None

SENSOR_FIELDS = (
    "facial_asymmetry_percentage", "oral_droop_percentage", "left_eye_openness_px",
    "right_eye_openness_px", "heart_rate_bpm", "respiratory_rate_bpm",
    "oxygen_saturation_percentage", "systolic_blood_pressure_mmhg",
    "diastolic_blood_pressure_mmhg",
)

DEFAULT_STATE: dict[str, Any] = {
    "asama": "form", "tc_input": "", "ad_input": "", "soyad_input": "",
    "age_input": 25, "gender_selectbox": "Belirtmek İstemiyorum", "kvkk_checkbox": False,
    "send_tc": "", "send_name": "", "send_surname": "", "send_gender": 0,
    "anonim_token": "", "olcum_thread": None, "olcum_kuyrugu": None,
    "olcum_sonuc": None, "olcum_hata": None, "api_hata": None,
}
for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


def css() -> str:
    return """<style>
    :root{color-scheme:dark!important}
    html,body,[data-testid=\"stAppViewContainer\"],[data-testid=\"stApp\"],.main{background:#080E0E!important;color:#E7F1EF!important}
    [data-testid=\"stHeader\"]{background:#080E0E!important}
    [data-testid=\"stToolbar\"]{visibility:hidden}
    .main .block-container{max-width:760px;margin:2rem auto;background:#0F1717;border:1px solid #20302E;border-radius:20px;padding:2.6rem 2.8rem!important;box-shadow:0 12px 32px rgba(16,31,28,.20)}
    .eyebrow,.step,.status{font:700 .75rem monospace;letter-spacing:.13em;text-transform:uppercase;color:#7FA19C!important}
    .title{font-size:1.9rem;font-weight:800;color:#E7F1EF!important}.status{text-align:right;color:#2DD4BF!important}.step{display:block;border-bottom:1px solid #20302E;padding-bottom:.85rem;margin:1.6rem 0}
    .clinical-divider{height:3px;margin:1.45rem 0 2rem;border-radius:999px;background:linear-gradient(90deg,#20302E 0%,#2DD4BF 18%,#2DD4BF 82%,#20302E 100%);box-shadow:0 0 12px rgba(45,212,191,.22)}
    .card{background:#0B1414;border:1px solid #20302E;border-radius:14px;padding:1.3rem}.card-title{font-size:1.35rem;font-weight:800;color:#E7F1EF!important}.card-copy{color:#7FA19C!important;line-height:1.6;margin-top:.4rem}.warning{color:#F87171!important}.footer{text-align:center;color:#7FA19C!important;font-size:.8rem;margin-top:1.5rem}
    div[data-baseweb=\"input\"],div[data-baseweb=\"select\"]>div{background:#0B1414!important;border-color:#20302E!important}input{color:#E7F1EF!important;-webkit-text-fill-color:#E7F1EF!important}
    [data-testid=\"baseButton-primary\"],button[kind=\"primary\"]{background:#2DD4BF!important;color:#04201D!important;border:none!important;font-weight:800!important;border-radius:12px!important}
    [data-testid=\"baseButton-secondary\"],button[kind=\"secondary\"]{background:transparent!important;color:#7FA19C!important;border:1.5px solid #20302E!important;border-radius:12px!important}
    </style>"""


def ekg_svg(animated: bool) -> str:
    animation_class = "ekg-akiyor" if animated else ""
    path = "M0,30 L90,30 L98,34 L106,6 L114,52 L122,26 L132,22 L142,30 L180,30 L270,30 L278,34 L286,6 L294,52 L302,26 L312,22 L322,30 L360,30 L450,30 L458,34 L466,6 L474,52 L482,26 L492,22 L502,30 L540,30 L600,30"
    return (f'<svg class="ekg-cizgi {animation_class}" viewBox="0 0 600 60" '
            f'preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">'
            f'<path d="{path}" fill="none" stroke="#2DD4BF" stroke-width="2.5" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def valid_tc(value: str) -> bool:
    return bool(re.fullmatch(r"[1-9][0-9]{10}", value.strip()))


def valid_name(value: str) -> bool:
    return len(value.strip()) >= 2


def reset() -> None:
    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = value


def camera_worker(output: queue.Queue[dict[str, Any]]) -> None:
    try:
        if not CAMERA_SCRIPT.exists():
            output.put({"ok": False, "error": f"Kamera dosyası bulunamadı: {CAMERA_SCRIPT}"})
            return
        result = subprocess.run([sys.executable, str(CAMERA_SCRIPT)], capture_output=True, timeout=CAMERA_TIMEOUT_SECONDS, env=os.environ.copy())
        if result.returncode != 0:
            output.put({"ok": False, "error": result.stderr.decode("utf-8", errors="replace")[-500:] or "Kamera işlemi başarısız."})
            return
        measurement: dict[str, Any] | None = None
        for line in reversed(result.stdout.decode("utf-8", errors="replace").splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                candidate = json.loads(line)
                if isinstance(candidate, dict):
                    measurement = candidate
                    break
        if measurement is None:
            output.put({"ok": False, "error": "Kamera geçerli JSON ölçüm sonucu üretmedi."})
            return
        missing = [field for field in SENSOR_FIELDS if field not in measurement]
        if missing:
            output.put({"ok": False, "error": "Eksik sensör alanları: " + ", ".join(missing)})
            return
        output.put({"ok": True, "data": measurement})
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        output.put({"ok": False, "error": f"Kamera ölçüm hatası: {exc}"})
    except Exception as exc:
        output.put({"ok": False, "error": f"Beklenmeyen kamera hatası: {exc}"})


def start_measurement(reuse_patient_data: bool = False) -> None:
    if token_servis is None:
        st.session_state.api_hata = "token_servis.py yüklenemedi. KIOSK_SUPPORT_DIR ayarını kontrol edin."
        st.session_state.asama = "hata"
        return

    if reuse_patient_data:
        tc = st.session_state.send_tc
        name = st.session_state.send_name
        surname = st.session_state.send_surname
        gender = st.session_state.send_gender
    else:
        tc = st.session_state.tc_input.strip()
        name = st.session_state.ad_input.strip()
        surname = st.session_state.soyad_input.strip()
        gender = {"Erkek": 1, "Kadın": 2, "Belirtmek İstemiyorum": 0}[st.session_state.gender_selectbox]

    if not (valid_tc(tc) and valid_name(name) and valid_name(surname)):
        st.session_state.api_hata = "Kimlik bilgileri eksik veya geçersiz."
        st.session_state.asama = "hata"
        return

    st.session_state.send_tc = tc
    st.session_state.send_name = name
    st.session_state.send_surname = surname
    st.session_state.send_gender = gender
    if not reuse_patient_data or not st.session_state.anonim_token:
        st.session_state.anonim_token = token_servis.anonim_token_uret()
    st.session_state.olcum_sonuc = None
    st.session_state.olcum_hata = None
    st.session_state.api_hata = None
    st.session_state.asama = "olcum"
    output: queue.Queue[dict[str, Any]] = queue.Queue()
    st.session_state.olcum_kuyrugu = output
    thread = threading.Thread(target=camera_worker, args=(output,), daemon=True)
    st.session_state.olcum_thread = thread
    thread.start()


def read_camera_queue() -> None:
    output = st.session_state.olcum_kuyrugu
    if output is None:
        return
    try:
        while True:
            event = output.get_nowait()
            if event.get("ok"):
                st.session_state.olcum_sonuc = event["data"]
            else:
                st.session_state.olcum_hata = str(event.get("error", "Ölçüm hatası."))
    except queue.Empty:
        pass


def send_measurement(measurement: dict[str, Any]) -> tuple[bool, str]:
    payload: dict[str, Any] = {"tc_kimlik": st.session_state.send_tc, "ad": st.session_state.send_name, "soyad": st.session_state.send_surname, "age": int(st.session_state.age_input), "gender": st.session_state.send_gender, "hasta_token": st.session_state.anonim_token}
    for field in SENSOR_FIELDS:
        payload[field] = measurement[field]
    if "measurement_confidence_score" in measurement:
        payload["measurement_confidence_score"] = measurement["measurement_confidence_score"]
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    try:
        response = requests.post(API_ENDPOINT, json=payload, headers=headers, timeout=35)
        return (True, "") if response.status_code in (200, 201) else (False, f"Sunucu hatası ({response.status_code}): {response.text[:400]}")
    except requests.RequestException as exc:
        return False, f"Sunucu bağlantı hatası: {exc}"


st.markdown(css(), unsafe_allow_html=True)
read_camera_queue()
left, right = st.columns([5, 1.3])
with left:
    st.markdown('<div class="eyebrow">Hasta Kayıt Noktası</div><div class="title">Poliklinik Kabul</div>', unsafe_allow_html=True)
with right:
    st.markdown('<div class="status">LOCAL · SECURE</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="clinical-divider" aria-hidden="true"></div>',
    unsafe_allow_html=True,
)

if st.session_state.asama == "form":
    st.markdown('<div class="step">Adım 1 / 2 — Kimlik Bilgileri ve Onay</div>', unsafe_allow_html=True)
    tc = st.text_input("T.C. Kimlik No", max_chars=11, key="tc_input")
    first, second = st.columns(2)
    with first:
        name = st.text_input("Adı", key="ad_input")
    with second:
        surname = st.text_input("Soyadı", key="soyad_input")
    age_column, gender_column = st.columns(2)
    with age_column:
        st.number_input("Yaşınız", min_value=0, max_value=120, step=1, key="age_input")
    with gender_column:
        st.selectbox("Cinsiyetiniz", ["Erkek", "Kadın", "Belirtmek İstemiyorum"], key="gender_selectbox")
    approved = st.checkbox("KVKK Veri Gizliliği Sözleşmesi'ni kabul ediyorum.", key="kvkk_checkbox")
    if tc and not valid_tc(tc):
        st.markdown('<div class="warning">T.C. Kimlik No 11 haneli olmalıdır.</div>', unsafe_allow_html=True)
    ready = valid_tc(tc) and valid_name(name) and valid_name(surname) and approved
    if st.button("Ölçümü Başlat", type="primary", disabled=not ready, use_container_width=True):
        start_measurement()
        st.rerun()
elif st.session_state.asama == "olcum":
    st.markdown('<div class="step">Adım 2 / 2 — Temassız Ölçüm</div>', unsafe_allow_html=True)
    thread = st.session_state.olcum_thread
    if thread is not None and thread.is_alive():
        st.markdown('<div class="card"><div class="card-title">Ölçüm yapılıyor</div><div class="card-copy">Lütfen kameraya sabit bakın ve işlem tamamlanana kadar bekleyin.</div></div>', unsafe_allow_html=True)
        time.sleep(0.5)
        st.rerun()
    elif st.session_state.olcum_hata:
        st.session_state.api_hata, st.session_state.asama = st.session_state.olcum_hata, "hata"
        st.rerun()
    elif isinstance(st.session_state.olcum_sonuc, dict):
        success, error = send_measurement(st.session_state.olcum_sonuc)
        st.session_state.asama = "basarili" if success else "hata"
        st.session_state.api_hata = error
        st.rerun()
elif st.session_state.asama == "basarili":
    st.markdown(
        '<div class="card">'
        '<div class="card-title">Ölçümünüz başarıyla tamamlandı</div>'
        '<div class="card-copy">Kaydınız güvenli şekilde oluşturuldu. Lütfen bekleme alanına geçiniz.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button("Yeni Hasta Kaydı", type="primary", use_container_width=True):
        reset()
        st.rerun()
elif st.session_state.asama == "hata":
    st.markdown(f'<div class="card"><div class="card-title">Kayıt tamamlanamadı</div><div class="card-copy">{st.session_state.api_hata or "Bilinmeyen hata."}</div></div>', unsafe_allow_html=True)
    retry_measurement, retry_send, reset_column = st.columns(3)
    with retry_measurement:
        if st.button("Ölçümü Yeniden Başlat", type="primary", use_container_width=True):
            # Kimlik ve demografik bilgiler session state içinde korunur.
            st.session_state.olcum_sonuc = None
            st.session_state.olcum_hata = None
            st.session_state.api_hata = None
            start_measurement(reuse_patient_data=True)
            st.rerun()
    with retry_send:
        if st.button("Tekrar Gönder", use_container_width=True) and isinstance(st.session_state.olcum_sonuc, dict):
            success, error = send_measurement(st.session_state.olcum_sonuc)
            st.session_state.asama = "basarili" if success else "hata"
            st.session_state.api_hata = error
            st.rerun()
    with reset_column:
        if st.button("Baştan Başla", use_container_width=True):
            reset()
            st.rerun()
st.markdown('<div class="footer">Bu kiosk yalnızca kayıt ve ölçüm içindir. Klinik değerlendirme doktor ekranında yapılır.</div>', unsafe_allow_html=True)
