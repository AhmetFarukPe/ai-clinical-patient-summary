# 🎥 AI-Powered Clinical Contactless Vital Sign & Facial Geometry Engine (`kamera_sensor.py`)

Bu modül, hastanelerin ve polikliniklerin check-in noktalarında çalışmak üzere tasarlanmış, **Yapay Zeka Destekli Muayene Öncesi Ön Teşhis Karar Destek Sistemi**'nin çekirdek donanım/sensör motorudur. Standart bir web kamerası (RGB) üzerinden, hastaya hiçbir fiziksel temas uygulamadan 20 saniye içinde hayati medikal parametreleri ve yüz geometrisi anomalilerini bilgisayarlı görü algoritmalarıyla hesaplar.

---

## 🔬 Çalışma Mekanizması ve Klinik Metrikler

Modül çalıştırıldığında OpenCV ve MediaPipe Face Mesh kütüphanelerini kullanarak gerçek zamanlı bir **Head-Up Display (HUD)** ekranı açar. 15 saniyelik tarama döngüsü boyunca şu 7 hayati parametreyi eş zamanlı olarak hesaplar ve filtreler:

### 1. Yüz ve Ağız Geometrisi (Nörolojik Takip)
*   **Facial Asymmetry Index (%):** MediaPipe Face Mesh landmark'ları (sağ/sol yanak, göz ve alın koordinatları) üzerinden yüzün simetri eksenindeki milimetrik sapmaları izler.
*   **Oral Droop Percentage (%):** Dudak kenarı koordinatlarının (Landmark 61, 291, 0, 17) horizontal düzleme göre asimetrisini ölçerek olası inme (fasiyel paralizi/felç) belirtilerini yakalar.
*   **Eye Openness (Left/Right px):** Sağ ve sol göz kapaklarının açıklık oranlarını piksel tabanlı olarak takip ederek ptozis (göz kapağı düşüklüğü) durumunu kontrol eder.

### 2. Temassız Yaşamsal Bulgular (rPPG & Hemodinamik Motor)
*   **Heart Rate (Nabız - bpm):** Alın ve yanak bölgelerindeki kılcal damarlardan geçen kan hacminin oluşturduğu mikroskobik renk değişimlerini (Işık absorbsiyonu flüktüasyonları) Remote Photoplethysmography (rPPG) sinyal işleme algoritmalarıyla yakalar.
*   **Respiratory Rate (Solunum - rpm):** Göğüs kafesi veya omuz hattındaki periyodik mikro-hareket frekanslarını ya da yüzdeki mikro-termal renk dalgalanmalarını izleyerek dakikadaki solunum sayısını hesaplar.
*   **Oxygen Saturation (SpO2 %):** rPPG sinyalindeki kırmızı ve mavi ışık absorbsiyon oranlarının (AC/DC oranları) hemodinamik kalibrasyon formülleriyle işlenmesi sonucu kandaki oksijen doygunluğunu tahmin eder.
*   **Blood Pressure (Kan Basıncı - mmHg):** Hesaplanan nabız dalga hızı, genlik analizleri ve hastanın yaş/cinsiyet demografik risk faktörlerinin matematiksel birleştirilmesiyle sistolik (büyük) ve diyastolik (küçük) tansiyon değerlerini simüle eder.

---

## 📡 Veri Akışı ve Pipeline Mimarisi

1.  **Frontend Tetiklemesi:** Kiosk ekranı (`interface1.py`), hastanın onayını aldıktan sonra işletim sisteminin global Python motoru üzerinden bu scripti bir `subprocess` (alt süreç) olarak ateşler.
2.  **Güvenlik Protokolü:** Kiosk, hastanın kimlik bilgilerinden tamamen arındırılmış benzersiz 8 haneli `HASTA_TOKEN` bilgisini işletim sistemi çevre değişkeni (`os.environ`) olarak bu sensöre paslar.
3.  **Hatasız Çıktı Modu (Byte-Streaming):** Kamera 20. saniyede taramayı bitirdiğinde, terminale herhangi bir deşifre hatası yaratmayacak şekilde saf ASCII uyumlu, temiz ve tek satırlık bir **JSON dizisi** basar ve kendini otomatik olarak imha eder (`sys.exit(0)`).

```json
{
  "facial_asymmetry_percentage": 4,
  "oral_droop_percentage": 2,
  "left_eye_openness_px": 12.4,
  "right_eye_openness_px": 12.2,
  "heart_rate_bpm": 74,
  "respiratory_rate_bpm": 16,
  "oxygen_saturation_percentage": 98,
  "systolic_blood_pressure_mmhg": 122,
  "diastolic_blood_pressure_mmhg": 82,
  "measurement_confidence_score": 96
}
```

---

## 🛠️ Bağımlılıklar ve Geliştirici Notları

Modülün kütüphane çakışmalarından (Dependency Hell) uzak durması için sunucu katmanından bağımsız olarak **Global Python 3.12+** binary'si ile çalıştırılması tasarlanmıştır.

### Gerekli Paketler:
```bash
pip install opencv-python mediapipe numpy
```

### Klavye Kısayolları (Manuel Kontrol):
*   `[R]`: Ölçüm matrislerini ve 15 saniyelik zamanlayıcıyı sıfırlar, taramayı baştan başlatır.
*   `[Q]`: Kamera penceresini güvenle kapatır ve alt süreci sonlandırır.
---

## 🪟 Windows Cross-Platform & Kamera İzni Çözüm Notu

Bu modül Linux (Pop!_OS) üzerinde Wayland/X11 yerel video sürücüleriyle kararlı çalışacak şekilde optimize edilmiştir. Projenin jüri sunumu veya dağıtımı **Windows** bir işletim sistemi üzerinde gerçekleştirilecekse, OpenCV'nin Windows arka plan kamera izin sistemine (Media Foundation) takılmaması ve `cv2.VideoCapture` kilidine düşmemesi için şu adımlar takip edilmelidir:

### 🛠️ Windows Kamera Erişim Düzeltmesi:
Kod içerisindeki standart kamera başlatma satırı (`cv2.VideoCapture(0)`) Windows platformlarında donanım izin uyuşmazlığı yaratırsa, video yakalama backend motoru zorunlu olarak **DirectShow (CAP_DSHOW)** moduna kalibre edilmelidir. 

`kamera_sensor.py` içindeki ilgili satırı şu şekilde güncellemeniz sorunu %100 çözecektir:

```python
# Linux Varsayılan: cap = cv2.VideoCapture(0)
# Windows İzin & Hız Düzeltmesi (DirectShow API):
import platform
if platform.system() == "Windows":
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
else:
    cap = cv2.VideoCapture(0)
```

### 🔒 Gizlilik ve Sistem İzinleri:
Windows Ayarları -> Gizlilik ve Güvenlik -> Kamera sekmesinden **"Uygulamaların kameranıza erişmesine izin ver"** ve **"Masaüstü uygulamalarının kameranıza erişmesine izin ver"** seçeneklerinin (PyCharm veya çalıştırılan Terminal için) aktif olduğundan emin olunmalıdır.
