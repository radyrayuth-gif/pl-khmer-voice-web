# 🌟 PL Khmer Voice - SRT & TTS Studio (Web Edition)

កម្មវិធីបកប្រែ Subtitle (Chinese -> Khmer) និងបង្កើតសំឡេងអានបែបភាពយន្ត (Khmer TTS) កំណែ **Web Application** ទំនើប រត់លើ Browser បានយ៉ាងរលូន។

---

## 🚀 របៀបបើកដំណើរការ (How to Run)

### វិធីទី១៖ ចុចបើកដោយផ្ទាល់ (ងាយស្រួលបំផុត)
* ចូលទៅកាន់ Folder គម្រោង `e:\Bong Pav\SRT+TTS Web`
* ចុចពីរដង (Double-click) លើ file **`run_web.bat`**
* Browser នឹងបើកទៅកាន់ **`http://localhost:8000`** ដោយស្វ័យប្រវត្តិ!

---

### វិធីទី២៖ បើកតាម Terminal / Command Prompt
```bash
python server.py
```
បន្ទាប់មកបើក Browser (Chrome, Edge, Brave...) វាយអាសយដ្ឋាន៖
```
http://localhost:8000
```

---

## ✨ លក្ខណៈពិសេសចម្បងៗ (Key Features)

1. **AI Subtitle Translation (Google Gemini 3.5 Flash Lite):**
   - ប្រើម៉ូដែល Gemini ចុងក្រោយបង្អស់ (ល្បឿនលឿន & សន្សំកូតា Quota)
   - វិភាគសាច់រឿងទូទាំងរឿង (Global Character Casting)
   - បែងចែកតួអង្គ និងភេទ (Gender & Character Diarization) ដោយស្វ័យប្រវត្តិ
   - ការពារការបាត់បន្ទាត់ (Zero-Drift Fallback)

2. **Khmer Neural TTS (Edge-TTS):**
   - សំឡេងប្រុស៖ **Piseth - ពិសិដ្ឋ** (`km-KH-PisethNeural`)
   - សំឡេងស្រី៖ **Sreymom - ស្រីម៉ុម** (`km-KH-SreymomNeural`)
   - អាចកែសម្រួលល្បឿន (Speech Rate) និង Pitch តាមជួរ ឬទូទាំងរឿង

3. **Interactive Subtitle Editor Table:**
   - កែសម្រួលអត្ថបទបកប្រែជាភាសាខ្មែរបានផ្ទាល់លើតារាង (Live Inline Editing)
   - ចុចប្តូរភេទតួអង្គ (ប្រុស 👨 / ស្រី 👩) ភ្លាមៗ
   - ស្តាប់ Preview សំឡេងតាមបន្ទាត់នីមួយៗ (ចុច ▶️ លើជួរ)

4. **Synchronized Master Audio Player & Karaoke Auto-Sync:**
   - ផ្គុំសំឡេងទាំងអស់ចូលទៅក្នុង **Master Voiceover MP3** ដោយកំណត់ពេលវេលា (Timestamp) ត្រូវតាម Subtitle ១០០%
   - មុខងារ **Auto-Sync Table**: ពេលកំពុងចាក់ Master Audio តារាងនឹងរំកិល និង Highlight ជួរដែលកំពុងនិយាយដោយស្វ័យប្រវត្តិ

5. **Export & Download:**
   - ទាញយក **Master Voiceover MP3**
   - Export Subtitle ជាឯកសារ **`.srt`** (មាន Tag តួអង្គ ឬអក្សរសុទ្ធ)
   - រក្សាទុក និងបើកបន្តជាមួយ **`.progress.json`**

6. **ស្វ័យប្រវត្តិនាំចូល API Keys ពី Desktop App:**
   - ប្រព័ន្ធទាញយក API Keys និងការកំណត់ចាស់ពី Desktop App ដោយស្វ័យប្រវត្តិ មិនបាច់ចំណាយពេល Copy/Paste ឡើងវិញឡើយ។
