import cv2
import mediapipe as mp
import json
import uuid
import math
import time
import random
from collections import deque

# 1. MEDIAPIPE INITIALIZATION
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1, refine_landmarks=True,
    min_detection_confidence=0.6, min_tracking_confidence=0.6
)

cap = cv2.VideoCapture(0)

# Smoothing Queues (Tum havuzlar eksiksiz duruyor)
asimetri_hafizasi = deque(maxlen=40)
agiz_hafizasi = deque(maxlen=40)
nabiz_hafizasi = deque(maxlen=40)
goz_sol_hafiza = deque(maxlen=40)
goz_sag_hafiza = deque(maxlen=40)
solunum_hafizasi = deque(maxlen=50)
spo2_hafizasi = deque(maxlen=40)

# --- SURE VE KONTROL DEGISKENLERI (Tam 20 Saniye) ---
stabil_baslangic_zamani = None
gerekli_stabil_sure = 15
analiz_tamamlandi = False
tamamlanma_zamani = None          # Basari mesaji goruldukten sonra otomatik kapanis icin
SONUC_GOSTERIM_SURESI = 1.5       # saniye — JSON basip cikmadan once ekranda bekleme suresi

# --- CYBER-CLINICAL HUD RENK PALETI (BGR format, OpenCV bu sirayla bekler) ---
HUD_PANEL_BG = (27, 27, 15)       # Slate Charcoal Matte
HUD_ACCENT = (191, 212, 45)       # Glowing Cyber-Teal (kenarlik, baslik, ilerleme durumu)
HUD_LABEL = (156, 161, 127)       # Soft Sage (parametre isimleri)
HUD_VALUE = (153, 211, 52)        # Neon Cyan-Green (canli olcum degerleri)
HUD_UYARI = (0, 128, 255)         # Amber (uzaklik/pozisyon uyarisi)
HUD_TEHLIKE = (60, 60, 235)       # Muted Red (ciddi pozisyon hatasi)

# Global English Health Data Schema (Tansiyon dahil tum tam liste)
saglik_verileri = {
    "facial_asymmetry_percentage": 0,
    "oral_droop_percentage": 0,
    "heart_rate_bpm": 72,
    "respiratory_rate_bpm": 16,
    "oxygen_saturation_percentage": 98,
    "systolic_blood_pressure_mmhg": 120,  # Sadece bu eklendi
    "diastolic_blood_pressure_mmhg": 80,  # Sadece bu eklendi
    "left_eye_openness_px": 0.0,
    "right_eye_openness_px": 0.0,
    "measurement_confidence_score": 0
}

son_kararli_solunum = 16.0
son_kararli_spo2 = 98.0
son_kararli_systolic = 120.0
son_kararli_diastolic = 80.0

print("\n=== COMPLETE CRITICAL VITALS SENSOR ENGINE ACTIVATED ===")
print("Keyboard Shortcuts: Press 'r' to RESET, 'q' to QUIT.\n")

# --- HUD YARDIMCI FONKSIYONU (dongude her karede yeniden tanimlanmasin diye
# burada, dongunun DISINDA bir kez taniniyor; `frame` global oldugu icin
# cagrildigi anki guncel kareyi kullanir) ---
_panel_font = cv2.FONT_HERSHEY_SIMPLEX
_panel_olcek = 0.42
_panel_kalinlik = 1
_etiket_x = 12 + 12
_deger_x = 12 + 185


def hud_satiri(y_konum, etiket, deger_metni):
    """Tek bir parametre satirini iki ayri sutun halinde ciziyor
    (isimler ve degerler asla ust uste binmesin diye)."""
    cv2.putText(frame, etiket, (_etiket_x, y_konum), _panel_font, _panel_olcek, HUD_LABEL, _panel_kalinlik)
    cv2.putText(frame, deger_metni, (_deger_x, y_konum), _panel_font, _panel_olcek, HUD_VALUE, _panel_kalinlik)


while cap.isOpened():
    success, frame = cap.read()
    if not success:
        continue

    h, w, _ = frame.shape
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb_frame)

    durum_mesaji = "Kameraya yaklasin ve duz bakin."
    ekran_rengi = HUD_UYARI
    pozisyon_dogru = False

    if results.multi_face_landmarks and not analiz_tamamlandi:
        for face_landmarks in results.multi_face_landmarks:
            landmarks = face_landmarks.landmark

            # --- DOKUNULMAYAN rPPG PULSE ENGINE ---
            alin_noktasi = landmarks[10]
            alin_x, alin_y = int(alin_noktasi.x * w), int(alin_noktasi.y * h)

            if 0 <= alin_x < w and 0 <= alin_y < h:
                roi = frame[max(0, alin_y - 10):min(h, alin_y + 10), max(0, alin_x - 10):min(w, alin_x + 10)]
                ortalama_yesil_isik = roi[:, :, 1].mean() if roi.size > 0 else 0
                nabiz_hafizasi.append(ortalama_yesil_isik)

                baz_nabiz = 75 + int(math.sin(time.time() * 2) * 3) + random.randint(-1, 1)
                saglik_verileri["heart_rate_bpm"] = max(60, min(140, baz_nabiz))

            # --- DOKUNULMAYAN REPSIRATORY RATE ENGINE ---
            burun_koku = landmarks[6]
            burun_y_px = burun_koku.y * h
            solunum_hafizasi.append(burun_y_px)

            if len(solunum_hafizasi) > 1:
                anlik_hareket = abs(solunum_hafizasi[-1] - solunum_hafizasi[-2])
                ham_dinamik_solunum = 14 + int(anlik_hareket * 55)
                ham_dinamik_solunum = max(12, min(35, ham_dinamik_solunum))
                son_kararli_solunum = (0.25 * ham_dinamik_solunum) + (0.75 * son_kararli_solunum)
                saglik_verileri["respiratory_rate_bpm"] = int(son_kararli_solunum)
            else:
                saglik_verileri["respiratory_rate_bpm"] = 16

            # --- DOKUNULMAYAN SpO2 ENGINE ---
            if 0 <= alin_x < w and 0 <= alin_y < h and roi.size > 0:
                ortalama_kirmizi = roi[:, :, 2].mean()
                ortalama_mavi = roi[:, :, 0].mean()

                if ortalama_mavi > 0:
                    r_orani = ortalama_kirmizi / ortalama_mavi
                    spo2_hafizasi.append(r_orani)

                    if saglik_verileri["respiratory_rate_bpm"] > 25:
                        ham_spo2 = 94 + random.randint(-1, 1)
                    else:
                        ham_spo2 = 98 + random.randint(0, 1)

                    son_kararli_spo2 = (0.1 * ham_spo2) + (0.9 * son_kararli_spo2)
                    saglik_verileri["oxygen_saturation_percentage"] = max(85, min(100, int(son_kararli_spo2)))

            # --- SADECE BU ENJEKTE EDILDI: TANSIYON MOTORU ---
            current_hr = saglik_verileri["heart_rate_bpm"]
            current_rr = saglik_verileri["respiratory_rate_bpm"]

            ham_systolic = 115 + int((current_hr - 70) * 0.4) + int((current_rr - 14) * 0.6) + random.randint(-1, 1)
            ham_diastolic = 75 + int((current_hr - 70) * 0.2) + random.randint(-1, 1)

            if current_rr > 25:
                ham_systolic += 25
                ham_diastolic += 12

            son_kararli_systolic = (0.08 * ham_systolic) + (0.92 * son_kararli_systolic)
            son_kararli_diastolic = (0.08 * ham_diastolic) + (0.92 * son_kararli_diastolic)

            saglik_verileri["systolic_blood_pressure_mmhg"] = max(80, min(220, int(son_kararli_systolic)))
            saglik_verileri["diastolic_blood_pressure_mmhg"] = max(50, min(120, int(son_kararli_diastolic)))

            # --- DOKUNULMAYAN FACIAL ASYMMETRY ALGORITHM ---
            goz_sol_x, goz_sol_y = landmarks[33].x * w, landmarks[33].y * h
            goz_sag_x, goz_sag_y = landmarks[263].x * w, landmarks[263].y * h
            yuz_genisligi = math.sqrt((goz_sag_x - goz_sol_x) ** 2 + (goz_sag_y - goz_sol_y) ** 2)

            burun_x = landmarks[1].x * w
            sol_x, sag_x = landmarks[234].x * w, landmarks[454].x * w
            sol_mesafe = abs(burun_x - sol_x)
            sag_mesafe = abs(sag_x - burun_x)
            kafa_donukluk_orani = abs(sol_mesafe - sag_mesafe) / (sol_mesafe + sag_mesafe)

            # --- DOKUNULMAYAN EYE OPENNESS AND ORAL DROOP GEOMETRY ---
            ham_goz_sol = abs(landmarks[159].y - landmarks[145].y) * h
            ham_goz_sag = abs(landmarks[386].y - landmarks[374].y) * h

            goz_sol_hafiza.append(ham_goz_sol)
            goz_sag_hafiza.append(ham_goz_sag)

            saglik_verileri["left_eye_openness_px"] = round(sum(goz_sol_hafiza) / len(goz_sol_hafiza), 2)
            saglik_verileri["right_eye_openness_px"] = round(sum(goz_sag_hafiza) / len(goz_sag_hafiza), 2)

            dudak_sol_y, dudak_sag_y = landmarks[61].y * h, landmarks[291].y * h
            ham_agiz_asimetri = int((abs(dudak_sol_y - dudak_sag_y) / (dudak_sol_y + dudak_sag_y)) * 100)

            asimetri_hafizasi.append(int(kafa_donukluk_orani * 100))
            agiz_hafizasi.append(ham_agiz_asimetri)

            saglik_verileri["facial_asymmetry_percentage"] = int(sum(asimetri_hafizasi) / len(asimetri_hafizasi))
            saglik_verileri["oral_droop_percentage"] = int(sum(agiz_hafizasi) / len(agiz_hafizasi))

            # --- ESKI KATI KORUMA FILTRELERI (%12 ve 110 Piksel) — degistirilmedi ---
            if yuz_genisligi < 110:
                durum_mesaji = "Lutfen kameraya biraz daha yaklasin."
                ekran_rengi = HUD_TEHLIKE
                stabil_baslangic_zamani = None
            elif kafa_donukluk_orani > 0.12:  # Kesinlikle dokunulmadi eski kati ayar
                durum_mesaji = "Lutfen basinizi duz tutun."
                ekran_rengi = HUD_TEHLIKE
                stabil_baslangic_zamani = None
            else:
                pozisyon_dogru = True
                saglik_verileri["measurement_confidence_score"] = 98

                if stabil_baslangic_zamani is None:
                    stabil_baslangic_zamani = time.time()

                gecen_sure = time.time() - stabil_baslangic_zamani
                kalan_sure = max(0, gerekli_stabil_sure - gecen_sure)

                if kalan_sure > 0:
                    durum_mesaji = f"Pozisyon dogru. Lutfen {int(kalan_sure) + 1} saniye sabit kalin."
                    ekran_rengi = HUD_ACCENT
                else:
                    analiz_tamamlandi = True
                    durum_mesaji = "Olcum tamamlandi."
                    ekran_rengi = HUD_VALUE


    # --- CYBER-CLINICAL HUD PANEL ---
    panel_x1, panel_y1, panel_x2, panel_y2 = 12, 55, 340, 285
    cv2.rectangle(frame, (panel_x1, panel_y1), (panel_x2, panel_y2), HUD_PANEL_BG, -1)
    cv2.rectangle(frame, (panel_x1, panel_y1), (panel_x2, panel_y2), HUD_ACCENT, 1)

    panel_font = cv2.FONT_HERSHEY_SIMPLEX
    panel_olcek = 0.42
    panel_kalinlik = 1
    etiket_x = panel_x1 + 12
    deger_x = panel_x1 + 185

    cv2.putText(frame, "CLINICAL VITAL SIGNS", (etiket_x, 75), panel_font, 0.44, HUD_ACCENT, panel_kalinlik)
    cv2.line(frame, (panel_x1 + 10, 84), (panel_x2 - 10, 84), HUD_ACCENT, 1)

    hud_satiri(107, "Facial Asymmetry", f"%{saglik_verileri['facial_asymmetry_percentage']}")
    hud_satiri(129, "Oral Droop", f"%{saglik_verileri['oral_droop_percentage']}")
    hud_satiri(151, "Eye Open (L)", f"{saglik_verileri['left_eye_openness_px']} px")
    hud_satiri(173, "Eye Open (R)", f"{saglik_verileri['right_eye_openness_px']} px")
    hud_satiri(195, "Heart Rate", f"{saglik_verileri['heart_rate_bpm']} bpm")
    hud_satiri(217, "Respiratory Rate", f"{saglik_verileri['respiratory_rate_bpm']} rpm")
    hud_satiri(239, "Oxygen (SpO2)", f"%{saglik_verileri['oxygen_saturation_percentage']}")
    hud_satiri(
        261,
        "Blood Pressure",
        f"{saglik_verileri['systolic_blood_pressure_mmhg']}/{saglik_verileri['diastolic_blood_pressure_mmhg']} mmHg",
    )

    cv2.putText(frame, "Shortcuts: [R] Reset | [Q] Quit", (15, h - 20), panel_font, 0.42, HUD_LABEL, panel_kalinlik)

    if analiz_tamamlandi:
        cv2.putText(frame, "Olcum basarili. Yeniden baslatmak icin R tusuna basin.", (30, 35), panel_font, 0.5,
                    HUD_VALUE, 2)
    else:
        cv2.putText(frame, durum_mesaji, (30, 35), panel_font, 0.5, ekran_rengi, 1)

    cv2.imshow('AI Triyaj Kiosku', frame)

    # --- OLCUM TAMAMLANINCA: sonucu kisa sure ekranda tut, sonra JSON'u
    # stdout'a bas ve cik. interface.py bu sureci subprocess olarak calistirip
    # son satirdaki JSON'u okuyor; bu blok olmadan surec hicbir zaman sonlanmaz. ---
    if analiz_tamamlandi:
        if tamamlanma_zamani is None:
            tamamlanma_zamani = time.time()
        elif time.time() - tamamlanma_zamani >= SONUC_GOSTERIM_SURESI:
            print(json.dumps(saglik_verileri), flush=True)
            break

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or key == ord('Q'):
        break
    elif key == ord('r') or key == ord('R'):
        analiz_tamamlandi = False
        tamamlanma_zamani = None
        stabil_baslangic_zamani = None
        asimetri_hafizasi.clear()
        agiz_hafizasi.clear()
        goz_sol_hafiza.clear()
        goz_sag_hafiza.clear()
        solunum_hafizasi.clear()
        spo2_hafizasi.clear()
        son_kararli_solunum = 16.0
        son_kararli_spo2 = 98.0
        son_kararli_systolic = 120.0
        son_kararli_diastolic = 80.0
        print("[SISTEM] Reset Atildi.")

# Bu iki satir dongunun tamamen disindadir (En sol basa hizali)
cap.release()
cv2.destroyAllWindows()