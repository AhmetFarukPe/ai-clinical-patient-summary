# AI-Powered Clinical Pre-Diagnosis & Patient Summary Tool

Poliklinik hasta kabul sürecini desteklemek için geliştirilmiş yerel klinik yazılım prototipi.

Sistem; hasta bilgilerini kiosk üzerinden alır, kamera destekli ölçüm sürecini yürütür, ölçümleri FastAPI ve SQLite ile kaydeder, Groq AI üzerinden doktor için klinik ön değerlendirme özeti üretir ve React doktor dashboardunda gösterir.

> Bu proje klinik karar destek prototipidir. Kesin tanı koymaz, tedavi önermez ve hekim muayenesinin yerini tutmaz.

---

## Özellikler

- Streamlit tabanlı hasta kabul kiosku
- KVKK onay akışı
- Hasta bilgileri: T.C. Kimlik No, ad, soyad, yaş ve cinsiyet
- Kamera destekli yüz geometrisi ve vital ölçüm akışı
- FastAPI REST API
- SQLite yerel veritabanı
- Groq `llama-3.1-8b-instant` ile AI klinik ön tanı özeti
- React + Vite doktor dashboardu
- Doktor ekranında KVKK maskeli hasta isimleri
- Doktor dashboardunda 3 saniyelik otomatik veri yenileme
- Docker ile FastAPI backend çalıştırma
- Kiosk başarı ekranında klinik veri gösterilmez

---

## Sistem Mimarisi

```text
Streamlit Hasta Kiosku
        |
        | POST /api/v1/hasta-checkin
        v
FastAPI Backend
        |
        +--> SQLite Veritabanı
        |
        +--> Groq AI Klinik Özet
        |
        | GET /api/v1/doktor-paneli/kuyruk
        v
React Doktor Dashboardu
```

---

## Proje Yapısı

```text
ai_triyaj_kiosk/
├── App_Backend/
│   ├── app.py
│   ├── veri_tabani.py
│   ├── kamera_sensor.py
│   ├── token_servis.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── Kiosk_Client/
│   └── interface.py
│
├── Doctor_Dashboard/
│   ├── package.json
│   └── src/
│       ├── App.tsx
│       └── pages/
│           ├── ClinicalDashboard.tsx
│           └── ClinicalDashboard.css
│
├── docker-compose.yml
├── .env
└── README.md
```

---

## Gereksinimler

- Python 3.10 veya üzeri
- Node.js 20 veya üzeri
- npm
- Docker Engine ve Docker Compose
- Webcam
- Linux / Pop!_OS / Ubuntu önerilir

---

## Ortam Değişkenleri

Proje kökünde `.env` dosyası oluşturun:

```env
GROQ_API_KEY=gsk_BURAYA_GROQ_API_KEY
KIOSK_API_KEY=
```

`GROQ_API_KEY` AI klinik özet üretimi için kullanılır.

> `.env` dosyasını GitHub'a yüklemeyin.

---

## Python Ortamını Hazırlama

Proje kökünde:

```bash
cd ~/ai_triyaj_kiosk
python3 -m venv env
source env/bin/activate
```

Gerekli paketleri yükleyin:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install fastapi "uvicorn[standard]" requests pydantic streamlit
python3 -m pip install mediapipe==0.10.21 opencv-python==4.10.0.84
```

---

## Docker ile Backend Çalıştırma

Docker servisinin çalıştığından emin olun:

```bash
sudo systemctl enable --now docker
```

Backend'i Docker ile başlatın:

```bash
cd ~/ai_triyaj_kiosk
sudo docker compose up --build -d
```

Backend kontrolü:

```bash
curl http://127.0.0.1:8000/health
```

Beklenen sonuç:

```json
{"status":"ok"}
```

Docker loglarını izlemek için:

```bash
sudo docker compose logs -f backend
```

Backend'i durdurmak için:

```bash
sudo docker compose down
```

---

## Docker Olmadan Backend Çalıştırma

Önce Docker container çalışıyorsa portu kapatın:

```bash
sudo docker compose down
```

Sonra:

```bash
cd ~/ai_triyaj_kiosk
source env/bin/activate
cd App_Backend
python3 veri_tabani.py
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Health kontrolü:

```bash
curl http://127.0.0.1:8000/health
```

---

## Hasta Kioskunu Çalıştırma

Yeni bir terminal açın:

```bash
cd ~/ai_triyaj_kiosk
source env/bin/activate
cd Kiosk_Client
python3 -m streamlit run interface.py
```

Kiosk genelde burada açılır:

```text
http://localhost:8501
```

Hasta kioskunda:

1. Hasta bilgileri girilir.
2. KVKK onayı verilir.
3. Kamera ölçümü başlatılır.
4. Ölçümler FastAPI backend'e gönderilir.
5. Hasta yalnızca ölçümün tamamlandığı bilgisini görür.

Kiosk ekranında vital bulgular, AI özeti veya doktor klinik verileri gösterilmez.

---

## Doktor Dashboardunu Çalıştırma

Yeni bir terminal açın:

```bash
cd ~/ai_triyaj_kiosk/Doctor_Dashboard
npm install
npm run dev
```

Dashboard genelde burada açılır:

```text
http://localhost:5173
```

Doktor dashboardu şu endpoint’i her 3 saniyede bir çağırır:

```text
GET http://127.0.0.1:8000/api/v1/doktor-paneli/kuyruk
```

---

## API Endpointleri

### Sağlık Kontrolü

```text
GET /health
```

Örnek cevap:

```json
{
  "status": "ok"
}
```

### Hasta Kayıt ve Ölçüm Gönderimi

```text
POST /api/v1/hasta-checkin
```

Kiosk; kimlik, yaş, cinsiyet ve sensor ölçümlerini bu endpoint'e gönderir.

Başarılı cevap:

```json
{
  "status": "success"
}
```

### Doktor Paneli Hasta Kuyruğu

```text
GET /api/v1/doktor-paneli/kuyruk
```

Doktor paneli için şu verileri döndürür:

- KVKK maskeli hasta adı
- Yaş ve cinsiyet
- Yüz asimetrisi
- Oral düşüklük
- Sol / sağ göz açıklığı
- Nabız
- Solunum sayısı
- Oksijen satürasyonu
- Kan basıncı
- Ölçüm güven skoru
- AI klinik ön tanı özeti
- AI güven skoru

---

## Veri Gizliliği

- Doktor ekranında hasta isimleri maskelenir.
- Kiosk ekranında klinik veri gösterilmez.
- Groq isteğine doğrudan hasta adı, soyadı veya T.C. Kimlik No gönderilmez.
- Bu prototipte T.C. Kimlik No yerel SQLite veritabanında tutulur.
- Gerçek üretim kullanımı öncesinde şifreleme, erişim kontrolü, audit log, saklama politikası ve KVKK uyumluluk değerlendirmesi yapılmalıdır.

---

## Önerilen `.gitignore`

```gitignore
.env
env/
.venv/
__pycache__/
*.py[cod]
*.db
node_modules/
dist/
.vite/
.idea/
```

---

## Çalıştırma Sırası

```text
1. FastAPI Backend / Docker Backend
2. Streamlit Hasta Kiosku
3. React Doktor Dashboardu
```

Yerel adresler:

```text
Backend:   http://127.0.0.1:8000
Kiosk:     http://localhost:8501
Dashboard: http://localhost:5173
```

---

## Klinik Güvenlik Notu

Bu uygulama yalnızca ön değerlendirme ve klinik özet desteği sağlar.

- Kesin tanı koymaz.
- Tedavi veya ilaç önermez.
- Hekim muayenesinin yerini tutmaz.
- Tüm klinik kararlar yetkili sağlık profesyoneli tarafından verilmelidir.