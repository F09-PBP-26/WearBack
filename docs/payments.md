# Pembayaran demo dan Insta ship

Halaman drop-off menyediakan tombol **Pay now** setelah pembeli menyimpan alamat dan titik peta. Perubahan alamat harus disimpan kembali sebelum tombol aktif. Total pembayaran memakai harga yang tersimpan pada transaksi.

Pembayaran ini adalah simulasi: tidak ada penagihan, integrasi payment gateway, atau pemesanan kurir. Pembayaran mengubah status `ongoing` menjadi `paid` (**Awaiting seller**), menghapus tenggat pembayaran, dan mengurangi stok sesuai jumlah barang dalam satu transaksi database. Pembayaran oleh pembeli belum menyelesaikan pesanan.

Hanya pembeli pemilik transaksi yang dapat mengonfirmasi melalui POST dengan CSRF. Pesanan kedaluwarsa, pesanan tanpa alamat, stok yang tidak mencukupi, listing yang sudah dihapus, dan barang yang sedang dilelang tidak dapat dibayar. Permintaan ulang tidak mengurangi stok lagi. Alamat tidak dapat diubah setelah pembayaran atau pembatalan.

Dashboard penjual `/listings/mine/` menampilkan pesanan berstatus `paid` milik penjual pada bagian **Ready to complete**, termasuk pembeli dan alamat tujuan. Sekali tekan **Insta ship** langsung mengubah status menjadi `completed`, tanpa dialog konfirmasi tambahan atau tahap Shipping. Hanya pemilik listing yang dapat melakukan POST ke `/listings/orders/<transaction_id>/ship/`. Waktu penyelesaian tersimpan di `completed_at`, dan stok tidak dikurangi lagi. Tombol tidak tersedia untuk pembeli, penjual lain, atau pesanan yang belum dibayar.

Riwayat transaksi pembeli menampilkan **Awaiting seller** setelah pembayaran, lalu **Completed** setelah penjual menekan Insta ship. Pembeli langsung dapat membuka detail dan memberikan ulasan. Dashboard penjual menampilkan hasil pada **Recently completed**. Insta ship hanya menyelesaikan pesanan di aplikasi dan tidak memesan kurir. Status `delivered` tetap tersedia untuk riwayat lama. Listing dengan pesanan `paid` tidak dapat dihapus agar pesanan tetap terhubung ke penjual.

Terapkan migrasi hingga `0022_insta_ship_completes_orders`. Migrasi `0022` mengubah pesanan yang masih `shipping` menjadi `completed`, mengganti nama `shipped_at` menjadi `completed_at` sambil mempertahankan waktu konfirmasi, dan menghapus pilihan status Shipping. Jika waktu konfirmasi lama kosong, nilai `updated_at` dipakai sebagai waktu penyelesaian. Pesanan yang masih menunggu konfirmasi penjual tetap `paid`.

```powershell
env\Scripts\python.exe manage.py migrate
```

Pengujian alur checkout, alamat, pembayaran, tenggat, stok, dan kontrol akses:

```powershell
env\Scripts\python.exe manage.py test main.test_payments main.test_dropoff main.test_insta_ship_migration listings.test_shipping
```
