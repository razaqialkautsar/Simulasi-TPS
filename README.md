# Simulasi Kemacetan Akses Mall

Simulasi agent based modelling memakai Mesa untuk konflik antara:

- jalur lambat satu arah ke kiri,
- jalur keluar mall menuju jalur lambat,
- jalur masuk mall.

Website interaktif disediakan lewat Flask. User dapat mengatur volume mobil, volume motor, flow masuk mall, flow keluar mall, faktor kesabaran individu, dan seed simulasi.

## Menjalankan

```powershell
py -m pip install -r requirements.txt
py app.py
```

Buka:

```text
http://127.0.0.1:5000/
```

## Output Metrik

- `Kemacetan`: indeks gabungan dari kendaraan berhenti, spawn tertahan, dan total waktu tunggu.
- `Near collision`: kejadian ketika agen yang sudah tidak sabar memaksa masuk ke area konflik.
- `Spawn tertahan`: kendaraan yang gagal masuk simulasi karena area spawn masih penuh.
