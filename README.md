# WearBack

**"Wear It Back, Give It Back"**

WearBack adalah platform marketplace pakaian preloved yang membantu pengguna menjual pakaian yang masih layak pakai dengan mudah, sekaligus memberi kesempatan kedua bagi fashion item untuk terus dipakai. Lewat WearBack, pakaian yang tadinya menumpuk di lemari bisa berubah jadi penghasilan tambahan bagi penjual, sekaligus jadi opsi belanja yang lebih terjangkau dan ramah lingkungan bagi pembeli.

Proyek ini dibuat untuk memenuhi tugas **Proyek Tengah Semester - Pemrograman Berbasis Platform (CSGE602022)**, Fakultas Ilmu Komputer, Universitas Indonesia, Semester Gasal 2026/2027, dengan tema **Sustainable Living** (sub-tema: **Slow Fashion & Conscious Shopping**).

### Manfaat bagi Masyarakat
- Mengurangi limbah tekstil dengan memperpanjang siklus pakai pakaian.
- Membuka peluang penghasilan tambahan bagi penjual pakaian bekas.
- Menyediakan alternatif belanja fashion yang lebih terjangkau dan berkelanjutan.
- Memudahkan pengguna menemukan titik drop-off/pengiriman terdekat untuk menjual pakaian.

## Anggota Kelompok

| Nama | NPM |
|---|---|
| Niccola Geraldo Winaryo Durand | 2506619070 |
| Fathir Azka Dillafah | 2506539523 |
| Hudzaifah | 2506622840 |
| Albert Timmothy Ariajaya (Project Manager) | 2506656381 |
| Lynorexly Imanuel Tatipikalawan | 2506546932 |

## Daftar Modul & Pembagian Kerja

| No | Modul | Deskripsi | PIC |
|---|---|---|---|
| 1 | Manajemen Listing Pakaian | CRUD data listing pakaian preloved: unggah, edit, hapus, dan lihat detail pakaian yang dijual (nama, kategori, ukuran, kondisi, harga, foto). | Niccola Geraldo Winaryo Durand |
| 2 | Transaksi & Pesanan | CRUD proses transaksi: pembuatan pesanan, update status pesanan (diproses/dikirim/selesai), riwayat transaksi pengguna. | Fathir Azka Dillafah |
| 3 | Profil & Autentikasi Pengguna | CRUD data profil pengguna, sistem login/register, filter akses berbasis autentikasi (mis. data kontak hanya terlihat oleh pengguna yang sudah login). | Hudzaifah |
| 4 | Ulasan & Rating Penjual | CRUD ulasan dan rating terhadap penjual/produk setelah transaksi selesai. | Albert Timmothy Ariajaya |
| 5 | Lokasi Drop-off (Integrasi OpenStreetMap) | CRUD data titik drop-off/mitra pengiriman, ditampilkan di peta menggunakan data dari OpenStreetMap, dengan filter berdasarkan lokasi terdekat. | Lynorexly Imanuel Tatipikalawan |

## Sumber Data

- **Public API eksternal:** [OpenStreetMap](https://www.openstreetmap.org/) digunakan untuk menampilkan dan mencari titik drop-off/mitra pengiriman pakaian terdekat berdasarkan lokasi pengguna.
- **Data utama (listing pakaian, minimal 50 data):** Dataset sintetis yang dihasilkan menggunakan LLM, di-*seed* secara manual ke database (nama produk, kategori, ukuran, kondisi, harga, deskripsi).

## Peran Pengguna

1. **Pembeli** menjelajahi listing pakaian, melakukan transaksi, memberi ulasan/rating, mencari titik drop-off terdekat.
2. **Penjual** mengunggah dan mengelola listing pakaian, memproses pesanan yang masuk, melihat ulasan dari pembeli.
3. **Pengguna Umum (belum login)** hanya dapat melihat listing pakaian secara terbatas, tanpa akses ke fitur transaksi dan data kontak.

## Cara Menjalankan Proyek

### Prasyarat

- [Python](https://www.python.org/downloads/) 3.10 atau lebih baru
- `pip` (biasanya sudah termasuk dalam instalasi Python)
- [Git](https://git-scm.com/)

### Langkah Instalasi

1. **Klon repositori** dan masuk ke direktori proyek.

   ```bash
   git clone https://github.com/F09-PBP-26/WearBack.git
   cd WearBack
   ```

2. **Buat dan aktifkan virtual environment.**

   macOS/Linux:

   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

   Windows (PowerShell):

   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Pasang dependensi.**

   ```bash
   pip install -r requirements.txt
   ```

4. **Terapkan migrasi database.**

   ```bash
   python manage.py migrate
   ```

5. **Jalankan server pengembangan.**

   ```bash
   python manage.py runserver
   ```

Setelah server berjalan, buka [http://127.0.0.1:8000](http://127.0.0.1:8000) pada browser.

> **Catatan:** Secara default proyek menggunakan SQLite sehingga tidak memerlukan konfigurasi database tambahan. Untuk mode produksi (PostgreSQL), atur `PRODUCTION=true` beserta `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, dan `DB_PORT` pada berkas `.env`.

### Pemeriksaan dan Pengujian

```bash
python manage.py check   # memeriksa konfigurasi proyek
python manage.py test    # menjalankan test suite
```

## Mengelola Konten melalui Admin Page

Aktifkan virtual environment terlebih dahulu, lalu jalankan perintah berikut untuk membuat akun admin:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Buka [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin) dan masuk menggunakan akun superuser yang baru dibuat untuk mengelola data melalui halaman admin Django.

## Tautan Terkait

- Repositori Git: https://github.com/F09-PBP-26/WearBack
- Desain Figma: https://ristek.link/PBP2026-F09-Figma
- Tautan Deployment (PWS): *(isi setelah deploy, minimal saat Checkpoint 2)*

---
*Proyek Tengah Semester PBP Gasal 2026/2027 - Fakultas Ilmu Komputer Universitas Indonesia*
