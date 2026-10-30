# Pembayaran demo dan Insta ship

Halaman drop-off menyediakan tombol **Pay now** setelah pembeli menyimpan alamat dan titik peta. Perubahan alamat harus disimpan kembali sebelum tombol aktif. Total pembayaran memakai harga yang tersimpan pada transaksi.

Pembayaran ini adalah simulasi: tidak ada penagihan, integrasi payment gateway, atau pemesanan kurir. Pembayaran mengubah status `ongoing` menjadi `paid` (**Awaiting shipment**), menghapus tenggat pembayaran, dan mengurangi stok sesuai jumlah barang dalam satu transaksi database. Pembayaran oleh pembeli tidak mengonfirmasi pengiriman.

Hanya pembeli pemilik transaksi yang dapat mengonfirmasi melalui POST dengan CSRF. Pesanan kedaluwarsa, pesanan tanpa alamat, stok yang tidak mencukupi, listing yang sudah dihapus, dan barang yang sedang dilelang tidak dapat dibayar. Permintaan ulang tidak mengurangi stok lagi. Alamat tidak dapat diubah setelah pembayaran atau pembatalan.

Dashboard penjual `/listings/mine/` menampilkan pesanan berstatus `paid` milik penjual pada bagian **Ready to ship**, termasuk pembeli dan alamat tujuan. Penjual menekan **Insta ship**, memeriksa tujuan di dialog, lalu menekan **Confirm shipment** setelah mengirim barang. Hanya pemilik listing yang dapat melakukan POST ke `/listings/orders/<transaction_id>/ship/`. Status berubah menjadi `shipping`, waktu konfirmasi tersimpan di `shipped_at`, dan stok tidak dikurangi lagi. Tombol tidak tersedia untuk pembeli, penjual lain, atau pesanan yang belum dibayar.

Riwayat transaksi pembeli menampilkan **Awaiting shipment** setelah pembayaran, lalu **Shipping** setelah konfirmasi penjual. Dashboard penjual menampilkan hasil pada **Recently shipped**. Pengiriman yang ditampilkan adalah status aplikasi; Insta ship tidak memesan kurir. Status `delivered` dan `completed` tetap mengikuti alur yang sudah ada. Listing dengan pesanan `paid` atau `shipping` tidak dapat dihapus agar pesanan tetap terhubung ke penjual.

Terapkan migrasi `0020_transaction_shipping_status` dan `0021_seller_shipment_confirmation` bersama perubahan ini. Migrasi `0021` juga mengembalikan pesanan yang otomatis ditandai `shipping` oleh handler demo versi sebelumnya ke `paid`, berdasarkan pesan status spesifik versi lama. Konfirmasi pengiriman oleh penjual tidak diubah.

```powershell
env\Scripts\python.exe manage.py migrate
```

Pengujian alur checkout, alamat, pembayaran, tenggat, stok, dan kontrol akses:

```powershell
env\Scripts\python.exe manage.py test main.test_payments main.test_dropoff listings.test_shipping
```
