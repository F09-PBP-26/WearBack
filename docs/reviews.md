# Ulasan dan Rating — Albert Timmothy Ariajaya

## Pemetaan persyaratan

| Persyaratan | Implementasi |
| --- | --- |
| Models | `reviews/models.py`: Review, transaksi, produk, penulis, rating, komentar, tag, timestamp, constraint duplikat |
| Create | POST `/reviews/order/<transaction_id>/create/` |
| Read | GET `/reviews/`, GET `/transactions/<transaction_id>/review/` |
| Update | GET/POST `/reviews/<pk>/edit/` |
| Delete | GET konfirmasi, POST `/reviews/<pk>/delete/` |
| Form | `ReviewForm`, `ReviewFilterForm` pada `reviews/forms.py` |
| Template responsif | `reviews/layout.html` mewarisi `base.html`, komponen editor/results, Bootstrap 5.3.8 grid dan CSS desain WearBack |
| AJAX | `static/js/review-crud.js`: fetch POST CRUD, fetch GET filter dan pagination, pembaruan bagian halaman |
| Autentikasi | Semua endpoint data nyata memerlukan login; riwayat pesanan hanya untuk pembeli |
| Otorisasi | Edit/hapus hanya untuk penulis; penjual hanya membaca ulasan yang diterima |
| Filter database | Rating 1–5, pencarian nama barang/komentar, written/received, urutan, pagination 9 ulasan |

## Aturan data

- `delivered`: tombol Check details membuka detail; belum mengizinkan submit.
- `completed`: pembeli bisa mengulas produk yang benar-benar ditautkan ke transaksi saat checkout.
- Transaksi lama tanpa `listing_id` tetap terbaca, tetapi ulasan tidak diizinkan. Jangan mencocokkan otomatis berdasarkan nama.
- Satu ulasan untuk pasangan transaksi dan produk. Pembeli tidak boleh mengulas produknya sendiri.
- Rating 1–5, komentar opsional maksimal 500 karakter, tag terbatas Quality/Description/Delivery/Packaging.
- Form tidak menerima pemilik, produk, atau transaksi dari input pengguna. View menentukan semuanya dari database.
- `save_review()` menjalankan `full_clean()` sebelum `save()`. Pemanggilan `save()` Django biasa tidak otomatis menjalankan validasi model.
- CSRF aktif. GET hapus hanya menampilkan konfirmasi. AJAX memakai token dari form dan HTML hasil template dengan escaping bawaan Django.
- Endpoint preview lama tetap data contoh; bukan jalur CRUD atau data transaksi pengguna.
- Grid Bootstrap dimuat melalui CDN; diperlukan koneksi internet untuk stylesheet tersebut. Warna dan tipografi berasal dari CSS lokal.

## Menjalankan dan menguji

```powershell
.\env\Scripts\python.exe -m pip install -r requirements-dev.txt
.\env\Scripts\python.exe manage.py migrate
.\env\Scripts\python.exe -m coverage run manage.py test reviews --noinput
.\env\Scripts\python.exe -m coverage report
.\env\Scripts\python.exe manage.py runserver
```

Coverage hanya menghitung kode Python modul reviews, bukan template, JavaScript, atau kualitas demo. Target minimum lokal 85%; hasil aktual diukur oleh perintah di atas.

## Skenario demo / live coding

1. Siapkan dua akun berbeda (pembeli dan penjual) serta transaksi uji dengan produk terkait. Perubahan status pesanan tetap tanggung jawab modul transaksi.
2. Login sebagai pembeli. Transaksi delivered → Check details → tampil data pesanan dan informasi menunggu completed.
3. Gunakan transaksi completed yang memiliki listing. Pilih bintang, tag, tulis komentar, Submit review. Halaman diperbarui tanpa reload.
4. Ubah nilai dan komentar, Save changes. Buka My reviews dari menu profil untuk membaca hasil dari database.
5. Coba filter rating, pencarian produk, dan scope. Login sebagai penjual untuk melihat Received as seller.
6. Buka URL edit/hapus ulasan pembeli dengan akun lain: respons 404. Uji CSRF dan payload palsu terdapat di `test_crud.py`.
7. Hapus ulasan lewat konfirmasi; editor kembali ke keadaan kosong. Coba form dengan JavaScript dimatikan untuk fallback HTML.
8. Jelaskan alur URL → view → form validation → model validation → database → HTML/JSON. Tunjukkan constraint unik dan mengapa ID pemilik tidak berasal dari form.

Untuk penilaian kontribusi, gunakan commit sendiri dan pahami perubahan sebelum push. Dokumen dan pengujian ini tidak menggantikan pemahaman saat live coding.
