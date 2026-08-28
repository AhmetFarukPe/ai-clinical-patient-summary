"""FastAPI backend for the kiosk and doctor patient-summary dashboard.

Run: uvicorn app_fixed:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Literal

import requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from veri_tabani import DEFAULT_DB_FILE, initialize_database

MODEL_NAME = "llama-3.1-8b-instant"
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
KIOSK_API_KEY = os.environ.get("KIOSK_API_KEY")
DB_FILE = Path(os.environ.get("HASTANE_DB_FILE", str(DEFAULT_DB_FILE))).expanduser().resolve()
AI_OFFLINE_SUMMARY = (
    "Yapay Zeka ag baglantisi koptugu icin on teshis ozeti uretilemedi. "
    "Lutfen hastayi manuel muayene ediniz."
)

app = FastAPI(title="AI Patient Summary API", version="2.1.0")
app.add_middleware(
    CORSMiddleware,
    # Local development only. Restrict this to known HTTPS origins before deployment.
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class KioskOlcumPaketi(BaseModel):
    tc_kimlik: str = Field(pattern=r"^[1-9][0-9]{10}$")
    ad: str = Field(min_length=2, max_length=80)
    soyad: str = Field(min_length=2, max_length=80)
    age: int = Field(ge=0, le=130)
    gender: Literal[0, 1, 2]
    hasta_token: str = Field(min_length=8, max_length=128)
    facial_asymmetry_percentage: int = Field(ge=0, le=100)
    oral_droop_percentage: int = Field(ge=0, le=100)
    left_eye_openness_px: float = Field(ge=0, le=200)
    right_eye_openness_px: float = Field(ge=0, le=200)
    heart_rate_bpm: int = Field(ge=20, le=250)
    respiratory_rate_bpm: int = Field(ge=4, le=80)
    oxygen_saturation_percentage: int = Field(ge=50, le=100)
    systolic_blood_pressure_mmhg: int = Field(ge=50, le=260)
    diastolic_blood_pressure_mmhg: int = Field(ge=30, le=160)
    measurement_confidence_score: int | None = Field(default=None, ge=0, le=100)

    @field_validator("ad", "soyad")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Alan bos olamaz.")
        return cleaned


@contextmanager
def database_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def require_api_key(provided_key: str | None) -> None:
    if KIOSK_API_KEY and provided_key != KIOSK_API_KEY:
        raise HTTPException(status_code=401, detail="Gecersiz veya eksik X-API-Key.")


def mask_name(first_name: str, last_name: str) -> str:
    masked_first = first_name[:1] + "*" * max(4, len(first_name) - 1)
    masked_last = last_name[:1] + "*" * max(4, len(last_name) - 1)
    return f"{masked_first} {masked_last}"


def extract_json(content: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI yaniti JSON olarak cozumlenemedi.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("AI yaniti bir JSON nesnesi olmali.")
    return parsed


def generate_clinical_summary(paket: KioskOlcumPaketi) -> dict[str, Any]:
    """Create a physician-only summary without triage categorization."""
    if not GROQ_API_KEY:
        return {"klinik_on_tani_ozeti": AI_OFFLINE_SUMMARY, "ai_guven_skoru": 0}

    system_prompt = """
Sen hekimin kullandığı yapay zekâ destekli klinik ön değerlendirme aracısın.
Kesin tanı koyma, tedavi önerisi verme, triyaj rengi, öncelik kategorisi veya P-kodu üretme.
Yaş, cinsiyet ve şu yedi ölçüm grubunu kısa, tarafsız ve hekime yönelik biçimde özetle:
yüz asimetrisi; oral düşüklük; sol/sağ göz açıklığı; nabız; solunum; oksijen satürasyonu; kan basıncı.
Özet, bulguların olası klinik korelasyonunu belirtmeli ve hekim muayenesinin yerine geçmediğini söylemelidir.
İç düşünce zinciri üretme. Yalnızca tek geçerli JSON nesnesi döndür:
{"klinik_on_tanı_ozeti":"Türkçe klinik ön değerlendirme özeti", "ai_guven_skoru":0}
""".strip()
    user_prompt = (
        f"Yaş: {paket.age}; Cinsiyet: {paket.gender}; Yüz asimetrisi: %{paket.facial_asymmetry_percentage}; "
        f"Oral düşüklük: %{paket.oral_droop_percentage}; Sol göz: {paket.left_eye_openness_px} px; "
        f"Sağ göz: {paket.right_eye_openness_px} px; Nabız: {paket.heart_rate_bpm} bpm; "
        f"Solunum: {paket.respiratory_rate_bpm}/dk; SpO2: %{paket.oxygen_saturation_percentage}; "
        f"Tansiyon: {paket.systolic_blood_pressure_mmhg}/{paket.diastolic_blood_pressure_mmhg} mmHg; "
        f"Ölçüm güveni: %{paket.measurement_confidence_score or 0}."
    )
    try:
        response = requests.post(
            GROQ_ENDPOINT,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL_NAME, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0},
            timeout=20,
        )
        response.raise_for_status()
        choices = response.json().get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise RuntimeError("AI yanitinda choices alani bulunamadi.")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise RuntimeError("AI yanitinda metin bulunamadi.")
        parsed = extract_json(content)
        summary = parsed.get("klinik_on_tanı_ozeti")
        confidence = parsed.get("ai_guven_skoru")
        if not isinstance(summary, str) or not summary.strip() or isinstance(confidence, bool):
            raise RuntimeError("AI yanitinin alanlari gecersiz.")
        return {"klinik_on_tani_ozeti": summary.strip(), "ai_guven_skoru": max(0, min(100, int(confidence)))}
    except (requests.RequestException, ValueError, RuntimeError):
        return {"klinik_on_tani_ozeti": AI_OFFLINE_SUMMARY, "ai_guven_skoru": 0}


@app.on_event("startup")
def startup() -> None:
    initialize_database(DB_FILE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/hasta-checkin")
def hasta_checkin(paket: KioskOlcumPaketi, x_api_key: str | None = Header(default=None)) -> dict[str, str]:
    require_api_key(x_api_key)
    ai_result = generate_clinical_summary(paket)
    confidence = paket.measurement_confidence_score or 0
    try:
        with database_connection() as connection:
            connection.execute(
                """INSERT INTO hastalar (tc_kimlik, ad, soyad, age, gender) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tc_kimlik) DO UPDATE SET ad=excluded.ad, soyad=excluded.soyad, age=excluded.age, gender=excluded.gender""",
                (paket.tc_kimlik, paket.ad, paket.soyad, paket.age, paket.gender),
            )
            patient = connection.execute("SELECT id FROM hastalar WHERE tc_kimlik = ?", (paket.tc_kimlik,)).fetchone()
            if patient is None:
                raise RuntimeError("Hasta kaydi bulunamadi.")
            connection.execute(
                """INSERT INTO olcumler (hasta_id, hasta_token, facial_asymmetry_percentage, oral_droop_percentage, left_eye_openness_px, right_eye_openness_px, heart_rate_bpm, respiratory_rate_bpm, oxygen_saturation_percentage, systolic_blood_pressure_mmhg, diastolic_blood_pressure_mmhg, measurement_confidence_score, klinik_on_tani_ozeti, ai_guven_skoru)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(hasta_token) DO UPDATE SET hasta_id=excluded.hasta_id, facial_asymmetry_percentage=excluded.facial_asymmetry_percentage, oral_droop_percentage=excluded.oral_droop_percentage, left_eye_openness_px=excluded.left_eye_openness_px, right_eye_openness_px=excluded.right_eye_openness_px, heart_rate_bpm=excluded.heart_rate_bpm, respiratory_rate_bpm=excluded.respiratory_rate_bpm, oxygen_saturation_percentage=excluded.oxygen_saturation_percentage, systolic_blood_pressure_mmhg=excluded.systolic_blood_pressure_mmhg, diastolic_blood_pressure_mmhg=excluded.diastolic_blood_pressure_mmhg, measurement_confidence_score=excluded.measurement_confidence_score, klinik_on_tani_ozeti=excluded.klinik_on_tani_ozeti, ai_guven_skoru=excluded.ai_guven_skoru, olcum_tarihi=CURRENT_TIMESTAMP""",
                (patient["id"], paket.hasta_token, paket.facial_asymmetry_percentage, paket.oral_droop_percentage, paket.left_eye_openness_px, paket.right_eye_openness_px, paket.heart_rate_bpm, paket.respiratory_rate_bpm, paket.oxygen_saturation_percentage, paket.systolic_blood_pressure_mmhg, paket.diastolic_blood_pressure_mmhg, confidence, ai_result["klinik_on_tani_ozeti"], ai_result["ai_guven_skoru"]),
            )
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail="Veritabani kaydi tamamlanamadi.") from exc
    return {"status": "success"}


@app.get("/api/v1/doktor-paneli/kuyruk")
def doktor_paneli_kuyruk(x_api_key: str | None = Header(default=None)) -> list[dict[str, Any]]:
    require_api_key(x_api_key)
    try:
        with database_connection() as connection:
            rows = connection.execute(
                """SELECT o.hasta_token AS id, h.ad, h.soyad, h.age, h.gender, o.facial_asymmetry_percentage, o.oral_droop_percentage, o.left_eye_openness_px, o.right_eye_openness_px, o.heart_rate_bpm, o.respiratory_rate_bpm, o.oxygen_saturation_percentage, o.systolic_blood_pressure_mmhg, o.diastolic_blood_pressure_mmhg, o.measurement_confidence_score, o.klinik_on_tani_ozeti, o.ai_guven_skoru, CAST((julianday('now') - julianday(o.olcum_tarihi)) * 1440 AS INTEGER) AS wait_minutes FROM olcumler o INNER JOIN hastalar h ON h.id = o.hasta_id ORDER BY o.olcum_tarihi DESC"""
            ).fetchall()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail="Hasta özeti kuyruğu okunamadi.") from exc

    gender_labels = {0: "Belirtilmemiş", 1: "Erkek", 2: "Kadın"}
    return [{"id": row["id"], "masked_name": mask_name(row["ad"], row["soyad"]), "age": row["age"], "gender": gender_labels.get(row["gender"], "Belirtilmemiş"), "facial_asymmetry_percentage": row["facial_asymmetry_percentage"], "oral_droop_percentage": row["oral_droop_percentage"], "left_eye_openness_px": row["left_eye_openness_px"], "right_eye_openness_px": row["right_eye_openness_px"], "heart_rate_bpm": row["heart_rate_bpm"], "respiratory_rate_bpm": row["respiratory_rate_bpm"], "oxygen_saturation_percentage": row["oxygen_saturation_percentage"], "systolic_blood_pressure_mmhg": row["systolic_blood_pressure_mmhg"], "diastolic_blood_pressure_mmhg": row["diastolic_blood_pressure_mmhg"], "measurement_confidence_score": row["measurement_confidence_score"], "klinik_on_tani_ozeti": row["klinik_on_tani_ozeti"], "ai_guven_skoru": row["ai_guven_skoru"], "wait_minutes": max(0, row["wait_minutes"] or 0)} for row in rows]
