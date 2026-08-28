import { Activity, BrainCircuit, ChevronRight, HeartPulse, RefreshCw, ShieldCheck, Stethoscope, Wind } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import './ClinicalDashboard.css'

type PatientRecord = {
  id: string
  masked_name: string
  age: number
  gender: string
  facial_asymmetry_percentage: number
  oral_droop_percentage: number
  left_eye_openness_px: number
  right_eye_openness_px: number
  heart_rate_bpm: number
  respiratory_rate_bpm: number
  oxygen_saturation_percentage: number
  systolic_blood_pressure_mmhg: number
  diastolic_blood_pressure_mmhg: number
  measurement_confidence_score: number
  klinik_on_tani_ozeti: string | null
  ai_guven_skoru: number | null
  wait_minutes: number
}

const API_URL = 'http://127.0.0.1:8000/api/v1/doktor-paneli/kuyruk'

function VitalCard({ label, value, unit, icon: Icon }: { label: string; value: string; unit: string; icon: typeof Activity }) {
  return (
    <article className="vital-card">
      <div className="vital-label"><Icon size={15} /> {label}</div>
      <div className="vital-value">{value} <span>{unit}</span></div>
    </article>
  )
}

function Dashboard() {
  const [patients, setPatients] = useState<PatientRecord[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const loadQueue = useCallback(async () => {
    try {
      const response = await fetch(API_URL)
      if (!response.ok) throw new Error(`Sunucu yanıtı: ${response.status}`)
      const payload: unknown = await response.json()
      if (!Array.isArray(payload)) throw new Error('Sunucudan beklenen hasta listesi alınamadı.')
      setPatients(payload as PatientRecord[])
      setError(null)
      setLastUpdated(new Date())
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Hasta kuyruğu alınamadı.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadQueue()
    const refreshTimer = window.setInterval(() => void loadQueue(), 3000)
    return () => window.clearInterval(refreshTimer)
  }, [loadQueue])

  const selectedPatient = useMemo(
    () => patients.find((patient) => patient.id === selectedId) ?? patients[0] ?? null,
    [patients, selectedId],
  )

  return (
    <main className="clinical-shell">
      <header className="clinical-header">
        <div className="brand"><div className="brand-icon"><Stethoscope size={22} /></div><div><p>KLİNİK OPERASYON SİSTEMİ</p><h1>AI Pre-Diagnosis Dashboard</h1></div></div>
        <div className="header-actions"><div className="connection"><span /> Canlı hasta akışı</div><button onClick={() => void loadQueue()} className="refresh-button"><RefreshCw size={15} /> Yenile</button></div>
      </header>

      <section className="dashboard-grid">
        <section className="queue-panel">
          <div className="panel-heading"><div><p>POLİKLİNİK KAYIT AKIŞI</p><h2>Hasta Özet Kuyruğu</h2></div><span className="count-badge">{patients.length} aktif kayıt</span></div>
          <div className="ekg-line" aria-hidden="true"><svg viewBox="0 0 680 52" preserveAspectRatio="none"><path d="M0 26h92l9 4 10-23 9 40 10-21 13-4 12 4h95l9 4 10-23 9 40 10-21 13-4 12 4h95l9 4 10-23 9 40 10-21 13-4 12 4h95l9 4 10-23 9 40 10-21 13-4 12 4h100" /></svg></div>
          {error ? <div className="error-box">API bağlantı hatası: {error}<br /><small>FastAPI sunucusunun `http://localhost:8000` adresinde çalıştığını kontrol edin.</small></div> : null}
          <div className="queue-table-wrap"><table className="queue-table"><thead><tr><th>Hasta</th><th>Yaş / Cinsiyet</th><th>Vital Özet</th><th>Ölçüm</th><th /></tr></thead><tbody>
            {patients.map((patient) => <tr key={patient.id} className={selectedPatient?.id === patient.id ? 'selected-row' : ''} onClick={() => setSelectedId(patient.id)}><td><strong>{patient.masked_name}</strong><small>{patient.id} · {patient.wait_minutes} dk önce</small></td><td><strong>{patient.age}</strong><span>{patient.gender}</span></td><td><div className="vital-summary"><HeartPulse size={14} /> {patient.heart_rate_bpm} bpm <b>·</b> {patient.oxygen_saturation_percentage}% SpO₂ <b>·</b> {patient.systolic_blood_pressure_mmhg}/{patient.diastolic_blood_pressure_mmhg}</div></td><td><span className="confidence">%{patient.measurement_confidence_score} güven</span></td><td><ChevronRight size={18} /></td></tr>)}
            {!loading && patients.length === 0 ? <tr><td colSpan={5} className="empty-state">Henüz doktor ekranına düşen hasta kaydı yok.</td></tr> : null}
            {loading ? <tr><td colSpan={5} className="empty-state">Hasta kayıtları yükleniyor...</td></tr> : null}
          </tbody></table></div>
        </section>

        <aside className="case-panel">
          {selectedPatient ? <><div className="case-heading"><div className="case-heading-row"><div><p>KLİNİK VAKA GÖRÜNTÜLEYİCİ</p><h2>{selectedPatient.masked_name}</h2><span>{selectedPatient.id} · {selectedPatient.age} yaş · {selectedPatient.gender}</span></div><span className="confidence confidence-large">%{selectedPatient.measurement_confidence_score} ölçüm güveni</span></div></div>
            <section><h3><Activity size={16} /> 7 KRİTİK ÖLÇÜM</h3><div className="vitals-grid"><VitalCard label="Nabız" value={String(selectedPatient.heart_rate_bpm)} unit="bpm" icon={HeartPulse} /><VitalCard label="Solunum" value={String(selectedPatient.respiratory_rate_bpm)} unit="/dk" icon={Wind} /><VitalCard label="SpO₂" value={String(selectedPatient.oxygen_saturation_percentage)} unit="%" icon={Activity} /><VitalCard label="Kan Basıncı" value={`${selectedPatient.systolic_blood_pressure_mmhg}/${selectedPatient.diastolic_blood_pressure_mmhg}`} unit="mmHg" icon={HeartPulse} /><VitalCard label="Yüz Asimetrisi" value={String(selectedPatient.facial_asymmetry_percentage)} unit="%" icon={Activity} /><VitalCard label="Oral Düşüklük" value={String(selectedPatient.oral_droop_percentage)} unit="%" icon={Activity} /><VitalCard label="Göz Açıklığı" value={`${selectedPatient.left_eye_openness_px}/${selectedPatient.right_eye_openness_px}`} unit="px L/R" icon={Activity} /></div></section>
            <section className="ai-summary"><h3><BrainCircuit size={17} /> AI KLİNİK ÖN TANI ÖZETİ</h3><p>{selectedPatient.klinik_on_tani_ozeti ?? 'Bu kayıt için AI klinik özeti henüz üretilemedi.'}</p><div className="ai-footer"><ShieldCheck size={15} /> AI güven skoru: %{selectedPatient.ai_guven_skoru ?? 0}. Bu çıktı hekim muayenesinin yerini tutmaz.</div></section>
          </> : <div className="no-selection"><Stethoscope size={32} /><p>İncelemek için hasta kaydı seçin.</p></div>}
        </aside>
      </section>
      <footer>{lastUpdated ? `Son güncelleme: ${lastUpdated.toLocaleTimeString('tr-TR')}` : 'Bağlantı bekleniyor'} · Kişisel veriler KVKK kapsamında maskelenmiştir.</footer>
    </main>
  )
}

export default Dashboard
