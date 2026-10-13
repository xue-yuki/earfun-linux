# Tes pertama extension

1. Install lalu logout/login; enable `earfun@ell.local`.
2. Pastikan service active dan ikon headphone tampil di panel atas.
3. Buka menu: bandingkan baterai/mode dengan CLI / aplikasi iPhone.
4. ANC → Ambient → ANC: pastikan efek dan pilihan mode mengikuti readback.
5. Game on/off: pastikan toggle kembali sesuai balasan.
6. Level ANC: Strong/Balanced/Wind/Adaptive saat ANC aktif.
7. Spatial on/off: verifikasi readback dan efek suara.
8. Multipoint off/on: koneksi iPhone mungkin berubah, uji saat siap.
9. EQ Bass lalu Flat: perhatikan efek suara. Preset tidak otomatis diterapkan lagi.
10. Putuskan Bluetooth: setelah refresh / ≤30 detik baterai harus menjadi —;
    kontrol tidak aktif. Sambung lagi: status harus pulih.
11. Matikan service: menu memberi petunjuk restart, tanpa crash GNOME.
12. Disable/enable extension: tidak ada ikon atau signal handler duplikat.

Jika ada masalah kirim log service dan `gnome-extensions info earfun@ell.local`.
Popup memakai efek versi pertama, dengan data baterai asli. Selanjutnya perlu bukti advertisement
buka/tutup casing; status Connected sendiri tidak membuktikan lid event.

## Tes popup 0.3.0

1. Pilih Tes popup: cek posisi di pojok kanan atas area kerja (jarak 24 px dari
   tepi kanan dan atas, di bawah panel GNOME), serta nama dan baterai cocok dengan menu panel.
2. Cek badan casing tetap diam dan earbuds naik bergantian.
3. Popup ditutup otomatis setelah 5 detik; × dan Kontrol bekerja.
4. Putus/sambung EarFun: satu popup baru setelah status dibaca, tanpa duplikat
   setiap 30 detik.
5. Lock screen dan disable extension: popup/timer harus hilang.
6. Logout/login: service harus pulih otomatis.
7. Saat animasi GNOME dimatikan: tampilkan posisi akhir tanpa gerakan.
