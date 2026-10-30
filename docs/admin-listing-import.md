# Impor Listing melalui Django Admin

Admin dapat membuat banyak listing melalui CSV tanpa menambahkan item satu per satu. Akun harus aktif, memiliki status staff, dan memiliki izin `listings.add_listing`; superuser memiliki izin ini secara otomatis. Akses penjual di halaman marketplace tetap mengikuti aturan kepemilikan listing.

## Deployment PWS

Deploy kode yang mencakup fitur ini, lalu jalankan migrasi pada environment aplikasi yang terhubung ke database PWS:

```bash
python manage.py migrate
```

Migrasi `listings.0003_listingimportbatch` membuat tabel preview impor. Tidak ada dependency atau environment variable baru. Jangan menjalankan impor pada database lokal jika tujuannya menambahkan item ke PWS.

Masuk ke `/admin/` menggunakan username dan password admin Django. Buka **Listings → Import CSV**. Jika belum memiliki admin, buat superuser pada environment/database PWS mengikuti panduan autentikasi.

## Mengunggah CSV

1. Pilih **Download CSV template** dan ganti baris contoh dengan item yang akan ditambahkan.
2. Simpan sebagai CSV UTF-8 dengan pemisah koma. Batas unggahan adalah 500 item dan 2 MB.
3. Pilih file dan **Default seller**. Secara awal seller default adalah akun admin yang sedang masuk.
4. Pilih **Preview items**, periksa semua detail, lalu pilih **Confirm import**. **Cancel** tidak menambahkan item.

Kolom wajib: `name`, `price`, `category`, `size`, `condition`.

Kolom opsional: `seller`, `stock`, `image_url`, `description`, `brand`, `material`, `style`, `location`, `contact_email`.

| Kolom | Format |
| --- | --- |
| `name` | Nama item, maksimal 200 karakter. |
| `seller` | Username akun aktif yang sudah ada. Kosong/tidak disertakan memakai default seller. Username CSV mengesampingkan default seller. |
| `price` | Angka positif, maksimal 10 digit sebelum desimal dan 2 digit desimal. Contoh `75000`, `75000.50`, `75.000`, atau `"75.000,50"`. |
| `category` | `tops`, `bottoms`, `outerwear`, `shoes`, `legwear`, `accessories`. |
| `size` | Teks ukuran, maksimal 32 karakter, misalnya `Medium` atau `One size`. |
| `condition` | `like_new`, `great`, `good`, `fair`. |
| `stock` | Bilangan bulat 0–9999. Kosong/tidak disertakan memakai 1; 0 berarti item tidak tersedia. |
| `image_url` | URL HTTPS, maksimal 1000 karakter. Kosong memakai placeholder foto. |
| `contact_email` | Alamat email kontak yang dipublikasikan untuk anggota yang sudah masuk. Tidak otomatis memakai email akun seller. |

Kolom opsional lain mengikuti validasi form listing. Kolom yang tidak dikenal, termasuk `id`, `seller_id`, dan timestamp, ditolak. Jangan menambahkan kolom selain yang didukung. Gunakan tanda kutip untuk nilai yang mengandung koma, tanda kutip, atau baris baru; aplikasi spreadsheet biasanya melakukan ini otomatis. Baris kosong diabaikan.

Contoh:

```csv
name,seller,price,category,size,condition,stock,image_url,description
Cotton shirt,,75000,tops,Medium,good,2,https://example.com/shirt.jpg,"Blue shirt, cotton"
Denim jacket,,"125.000,50",outerwear,Large,great,1,,Lightly worn
```

## Validasi dan konfirmasi

- Unggahan hanya membuat preview, belum membuat listing. Preview hanya dapat dibuka atau dikonfirmasi oleh admin yang mengunggahnya dan berlaku selama 30 menit.
- Jika ada baris tidak valid, halaman menampilkan nomor baris CSV, kolom, dan pesan kesalahan. Seluruh file ditolak; perbaiki file dan unggah ulang.
- Seller dan detail item diperiksa kembali saat konfirmasi. Seller yang dihapus, dinonaktifkan, atau berganti username setelah preview akan memblokir impor.
- Semua listing, log penambahan Django admin, dan status konfirmasi disimpan dalam satu transaksi. Kegagalan penyimpanan membatalkan semuanya.
- Pada PostgreSQL PWS, preview dikunci selama konfirmasi. Mengirim ulang konfirmasi yang sama tidak membuat item duplikat. Setelah berhasil, isi preview dikosongkan dan penanda konfirmasi disimpan.
- Mengunggah file yang sama sebagai **impor baru** tetap membuat listing baru. Fitur ini tidak memperbarui listing lama dan tidak mencocokkan item berdasarkan nama.
- Preview kedaluwarsa yang belum dikonfirmasi dibersihkan ketika admin tersebut membuat preview baru.

## Pengujian

```powershell
env\Scripts\python.exe manage.py check
env\Scripts\python.exe manage.py makemigrations --check --dry-run
env\Scripts\python.exe manage.py test listings.test_admin_import
env\Scripts\python.exe manage.py test
```

Pengujian impor mencakup preview/konfirmasi, izin dan CSRF, seller per baris, harga rupiah, BOM UTF-8, CSV rusak, batas unggahan, validasi item, kedaluwarsa, seller yang berubah, rollback transaksi, log admin, dan pengiriman ulang konfirmasi.
