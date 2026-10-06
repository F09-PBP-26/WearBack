# Autentikasi WearBack

Autentikasi memakai `main.User` (turunan `AbstractUser`) dengan tabel `auth_user` yang sudah ada. Login lokal memakai email; username internal tetap tersedia untuk akun admin. Email dinormalisasi menjadi huruf kecil dan unik tanpa membedakan kapital. `SSOIdentity` menghubungkan subjek CAS UI dengan akun WearBack, bukan mencocokkan email secara otomatis.

## Instalasi baru

```powershell
env\Scripts\python.exe -m pip install -r requirements.txt
env\Scripts\python.exe manage.py migrate
env\Scripts\python.exe manage.py createsuperuser
env\Scripts\python.exe manage.py test
```

## Upgrade database lama

Backup database sebelum upgrade. Untuk deployment yang sudah menjalankan migrasi Django tetapi belum memiliki `main.0001_initial`, jalankan migrasi adopsi dengan model auth lama terlebih dahulu:

```powershell
$env:WEARBACK_ADOPT_AUTH = 'true'
env\Scripts\python.exe manage.py migrate main 0001 --skip-checks
Remove-Item Env:\WEARBACK_ADOPT_AUTH
env\Scripts\python.exe manage.py migrate
```

Pada shell Linux:

```bash
WEARBACK_ADOPT_AUTH=true python manage.py migrate main 0001 --skip-checks
python manage.py migrate
```

Flag ini hanya untuk perintah adopsi, jangan disimpan di `.env` atau dipakai untuk menjalankan server. Pemeriksaan sementara dilewati karena kedua model mewakili tabel yang sama selama transisi. Migrasi adopsi memeriksa kolom tabel user dan kedua tabel relasi; database dengan skema berbeda dihentikan untuk pemeriksaan manual. Migrasi auth harus sudah sampai `0012` sebelum adopsi. Tidak ada tabel user yang dihapus atau direset. ID, password, grup, izin admin lama, dan riwayat admin dipertahankan. Migrasi berikutnya menghentikan upgrade jika ada email duplikat setelah normalisasi; selesaikan konflik tersebut sebelum mencoba lagi. Rollback migrasi adopsi membutuhkan pemulihan backup.

Database lokal telah diupgrade; backup sebelum autentikasi berada di `env/backups/db-before-auth.sqlite3` (tidak masuk Git).

## Konfigurasi SSO UI

Konfigurasi dibaca dari `.env`, bukan `.env.prod`. Contoh nilai:

```dotenv
SSO_ENABLED=true
SSO_SERVER_URL=https://sso.ui.ac.id/cas2/
SSO_CAS_VERSION=2
SSO_SERVICE_URL=https://hudzaifah51-wearback.pws.cs.ui.ac.id/sso/callback/
```

Endpoint `/cas2/` mengikuti [dokumentasi library SSO UI dari RISTEK](https://github.com/RistekCSUI/django-sso-ui); versi protokol CAS tetap `2`. Path endpoint server berbeda dari versi protokol client. Jika `.env` atau environment deployment masih berisi `SSO_SERVER_URL=https://sso.ui.ac.id/cas/`, ubah menjadi `/cas2/` dan restart server. Jika belum siap, set `SSO_ENABLED=false`; login lokal tetap berjalan. Untuk lokal, kosongkan `SSO_SERVICE_URL` agar callback mengikuti host request. Service CAS mencakup query `state` yang acak; aturan service yang disetujui harus menerima callback `/sso/callback/` beserta query tersebut. Jika endpoint yang benar tetap menolak localhost, gunakan domain HTTPS deployment yang sudah disetujui pengelola UI/course.

Implementasi memakai `python-cas==1.7.2`, yaitu client protokol yang digunakan oleh ekosistem django-cas-ng, dengan view WearBack sendiri untuk mapping identitas dan linking akun. Sertifikat TLS selalu diverifikasi; request validasi memiliki timeout 8 detik. UI password tidak pernah dikirim ke WearBack. Callback hanya diterima untuk percobaan SSO di session browser yang sama, dengan state yang cocok dan masa berlaku sepuluh menit. Ticket diperiksa di server sebelum membuat/login akun. State langsung dikonsumsi, sehingga callback tidak bisa dipakai ulang.

Pada login SSO pertama, akun lokal dibuat dengan password yang tidak dapat dipakai. Nama dan email diambil dari respons CAS yang sudah diverifikasi; email mendukung atribut `mail`, `email`, `emailAddress`, dan `email_address` tanpa membedakan kapital. Profil akun SSO yang sudah ada diperbarui setiap login dari atribut yang tersedia. Pengguna SSO tidak diminta mengisi popup profil; jika provider tidak memberikan email, email tetap kosong, bukan ditebak dari username. Email yang sudah dimiliki akun WearBack lain menghentikan login dengan petunjuk linking; akun tidak digabung otomatis. Untuk menghubungkan akun lokal yang sudah ada, login menggunakan password akun tersebut lalu pilih `Link SSO UI` di navbar; proses linking memerlukan POST dengan CSRF dan callback dalam session pengguna yang sama. Satu identitas UI hanya dapat dimiliki satu akun WearBack.

`Log out` mengakhiri session WearBack saja. Session SSO UI tetap aktif, sehingga login SSO berikutnya bisa langsung berhasil. Global logout UI, verifikasi email, pengiriman email, dan reset password belum disediakan.

## Konfigurasi produksi

```dotenv
PRODUCTION=true
DEBUG=false
SECRET_KEY=<kunci-acak-yang-kuat>
ALLOWED_HOSTS=hudzaifah51-wearback.pws.cs.ui.ac.id
TRUST_PROXY_HTTPS=true
```

Aktifkan `TRUST_PROXY_HTTPS` hanya jika reverse proxy terpercaya menghapus header HTTPS dari client dan menetapkannya sendiri. Produksi membutuhkan SECRET_KEY sendiri, memakai cookie session/CSRF Secure, dan redirect HTTPS. Jangan mengganti SECRET_KEY ketika session perlu dipertahankan. Isi konfigurasi PostgreSQL `DB_*` seperti yang dijelaskan README.

Pembatasan percobaan menggunakan tabel `AuthThrottle`, sehingga semua worker memakai batas yang sama: sepuluh percobaan per sepuluh menit per IP/jenis endpoint, dengan batas tambahan per email untuk login. Alamat IP berasal dari `REMOTE_ADDR`; konfigurasi proxy harus memastikan nilainya sesuai untuk deployment. Kunci throttle berupa HMAC, bukan email/IP mentah. Counter kedaluwarsa dibersihkan saat request autentikasi berikutnya.

## Endpoint dan pengujian

- `POST /register/`: validasi profil/password/konfirmasi, membuat akun, langsung login.
- `POST /login/`: autentikasi email/password dan session Django.
- `POST /logout/`: logout lokal, wajib CSRF.
- `POST /profile/`: melengkapi profil pengguna yang sudah login.
- `GET /sso/login/`: memulai CAS login.
- `GET /sso/callback/`: memvalidasi state dan ticket CAS.
- `POST /sso/link/`: memulai linking akun lokal yang sudah login.

Form popup memakai CSRF dan menampilkan error per field tanpa meninggalkan halaman. Redirect setelah autentikasi hanya boleh ke host lokal aplikasi. Nama/email dipertahankan saat validasi gagal; password dibersihkan setelah error dari server. GET `/login/` dan `/register/` tetap membuka popup pada katalog.

```powershell
env\Scripts\python.exe manage.py check
env\Scripts\python.exe manage.py makemigrations --check --dry-run
env\Scripts\python.exe manage.py test
```

Test menggunakan database terpisah dan respons CAS yang dimock, termasuk parser XML CAS asli. Endpoint lama `/cas/` menolak callback localhost (`Application Not Authorized to Use CAS`). Gateway UI juga mengembalikan nginx `400 Bad Request` untuk User-Agent bawaan `python-requests`; client WearBack memakai `User-Agent: WearBack/1.0`. Pemeriksaan live dengan ticket dummy berhasil menerima XML CAS `INVALID_TICKET`, yang tetap ditolak sebagai autentikasi. Login dengan akun UI asli perlu dicoba lagi setelah restart server. Jangan menyimpan credential atau ticket CAS dalam log, source, maupun fixture.
