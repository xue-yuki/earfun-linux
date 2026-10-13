# EarFun Panel 0.3.0 — GNOME Shell 50

Extension panel atas untuk EarFun Air Pro 4i (TW230), dengan service Python lokal.
Versi awal ini menyediakan baterai kiri/kanan/casing, ANC, level ANC, game mode,
spatial audio, multipoint, dan preset EQ Flat/Bass/Vocal. Ikon tetap terlihat saat
perangkat terputus agar status dan petunjuk koneksi mudah ditemukan.

## Baru di 0.3.0

- Popup di pojok kanan atas work area monitor utama, berjarak 24 px dari tepi kanan
  dan atas, saat EarFun tersambung, sekali per transisi koneksi.
  Juga muncul sekali saat extension baru diaktifkan dengan
  earbuds yang sudah tersambung dan status siap.
- Memakai empat aset dan gerakan dari preview PERTAMA yang dipilih pengguna:
  popup naik/fade, efek tutup muncul, earbuds kiri/kanan naik bergantian,
  lalu baterai muncul. Pose tertutup/setengah terbuka hasil revisi tidak digunakan.
- Persentase kiri/kanan/casing berasal dari service, tidak ada angka demo.
  Field belum diketahui ditampilkan —. Popup menunggu status pertama selesai.
- Hilang setelah 5 detik; tombol × dan Escape menutup; tombol Kontrol membuka menu.
- Menu panel memiliki **Tes popup** saat EarFun tersambung.
- Animasi menghormati pengaturan animasi GNOME. Popup tidak muncul di lock screen,
  tidak mengambil fokus keyboard dan dibersihkan saat disable.
- Service membaca perubahan Connected dari BlueZ untuk refresh lebih cepat,
  dengan polling 30 detik sebagai cadangan.
- Kehilangan session D-Bus sekarang menghasilkan exit gagal; unit memakai
  Restart=always dengan jeda 5 detik dan tanpa batas jumlah restart. systemctl stop
  yang diminta pengguna tetap menghentikannya.

**Ini efek penyambutan bergaya 2D, bukan simulasi engsel fisik atau deteksi lid.**
Aset pertama disertakan tanpa retouch; ketidaksempurnaan tepi sumber tetap ada.
Belum ada deteksi tutup casing atau editor EQ 10 slider.

## Upgrade dari 0.2.0

Tidak perlu uninstall. Unduh/ekstrak ZIP baru dan jalankan installer di folder
0.3.0 dengan MAC dan channel yang sudah dikonfirmasi. Installer memperbarui lokasi
service dan extension yang sama. **Logout/login diperlukan** untuk mengganti
JavaScript extension yang sudah tercache, lalu enable UUID yang sama. Tutup/buka
menu atau gunakan Tes popup untuk verifikasi awal.

Service tidak otomatis mengubah mode, menulis EQ, atau memulihkan preset saat reconnect.
CLI dengan EQ 10 band tetap disertakan.

## Instalasi CachyOS / Arch

Paket `python-gobject` menyediakan Gio/GLib untuk Python sistem. Bluetooth dan
`bluez-deprecated-tools` sudah tersedia pada laptop yang digunakan saat pengujian.

```bash
sudo pacman -S --needed python-gobject
```

Unduh dan ekstrak ZIP dari [repo GitHub](https://github.com/xue-yuki/earfun-linux),
atau clone repo:

```bash
git clone https://github.com/xue-yuki/earfun-linux.git
cd earfun-linux
```

Buka terminal di folder proyek dan cari alamat Bluetooth perangkat:

```bash
python3 earfunctl.py devices
```

Sambungkan earbuds lewat pengaturan Bluetooth GNOME, lalu temukan channel SPP
melalui SDP. Ganti alamat contoh `02:00:00:00:00:01` dengan MAC perangkatmu:

```bash
python3 earfunctl.py discover --mac 02:00:00:00:00:01
```

Pasang menggunakan MAC yang sama dan channel dari hasil discovery.
Angka `1` berikut hanya contoh; ganti sesuai hasil SDP, jangan menebak channel:

```bash
python3 install.py --mac 02:00:00:00:00:01 --channel 1
```

Installer memeriksa GNOME 50 dan `/usr/bin/python3` dengan Gio sebelum memasang.
Jalankan installer **tanpa sudo**. Tidak perlu pip, venv, atau memasang APK.

Installer menyalin kode ke `~/.local/share/earfun-panel`, extension ke
`~/.local/share/gnome-shell/extensions/earfun@ell.local`, dan unit ke
`~/.config/systemd/user/earfun.service`. Default perangkat ada di
`~/.config/earfun/config.json`. XDG_DATA_HOME dan XDG_CONFIG_HOME didukung.

**Logout lalu login kembali** agar GNOME menemukan extension baru / memuat ulang
kode saat update. Setelah login:

```bash
gnome-extensions enable earfun@ell.local
```

Klik ikon headphone di panel atas. Service mengumpulkan status pada event koneksi BlueZ dan setiap 30 detik,
serta saat menu dibuka atau tombol Refresh dipilih. Koneksi diperiksa lewat BlueZ,
bukan dengan asumsi nama adapter hci0. Saat offline, service tidak membuka RFCOMM.

## Cara membaca hasil

- Persentase panel = baterai terendah dari earbuds yang datanya diketahui.
- Menu menampilkan baterai kiri, kanan, casing secara terpisah.
- `—` berarti belum tersedia / gagal dibaca; bukan 0%.
- Mode ANC dan toggle disinkronkan dengan balasan perangkat.
- Perubahan fitur terverifikasi hanya jika readback cocok.
- EQ hanya menunjukkan bahwa 10 frame terkirim. Efek suara telah dilaporkan
  berhasil oleh pemilik perangkat untuk preset Bass/Flat; tidak ada readback EQ.
- Preset Vocal masih perlu tes dengar. Tidak ada indikator “EQ aktif” yang mengaku
  sebagai hasil baca perangkat.
- Menutup/membuka casing tidak disimpulkan dari status Connected atau baterai.

## CLI tanpa mengetik MAC lagi

Default disimpan oleh installer. Dari folder ini:

```bash
python3 earfunctl.py status --full
python3 earfunctl.py noise anc
python3 earfunctl.py eq --preset bass
python3 earfunctl.py eq --preset flat
python3 earfunctl.py eq --gains=3,3,2,1,0,0,0,0,0,0
```

Default dapat diubah dengan:

```bash
python3 earfunctl.py configure --mac MAC --channel CHANNEL
systemctl --user restart earfun.service
```

MAC/channel eksplisit tetap didukung. Jika memilih MAC berbeda, channel default
perangkat lama tidak diwariskan. Saat menggunakan CLI untuk tes hardware, hentikan
service sementara supaya dua proses tidak membuka channel bersamaan:

```bash
systemctl --user stop earfun.service
# jalankan tes CLI
systemctl --user start earfun.service
```

## Diagnostik

```bash
systemctl --user status earfun.service --no-pager
journalctl --user -u earfun.service -n 40 --no-pager
gnome-extensions info earfun@ell.local
```

Jika extension error, lihat log GNOME:

```bash
journalctl -b -o cat /usr/bin/gnome-shell --no-pager
```

Tes service langsung, tanpa UI:

```bash
gdbus call --session --dest io.github.ell.EarFun --object-path /io/github/ell/EarFun --method io.github.ell.EarFun.GetState
```

`ModuleNotFoundError: gi`: pastikan paket python-gobject terpasang dan
`/usr/bin/python3 -c 'from gi.repository import Gio, GLib'` berhasil.
`Extension does not exist`: logout/login dahulu lalu enable lagi.
Tidak tersambung: sambungkan lewat pengaturan Bluetooth GNOME. Extension belum
menyediakan pairing atau koneksi otomatis.

## Menghapus

Dari folder unduhan:

```bash
python3 uninstall.py
```

Konfigurasi perangkat tetap disimpan. Logout/login jika kode extension masih tercache.

## Arsitektur

Extension GJS → session D-Bus `io.github.ell.EarFun` → Python Gio service →
protokol CLI → RFCOMM SPP. Bluetooth berjalan di worker thread tunggal per operasi;
permintaan saat sibuk ditolak, tidak ditumpuk. Status terakhir ditandai terputus
jika pemeriksaan BlueZ gagal. Tidak ada subprocess sinkron di GNOME Shell.

D-Bus API: `GetState() → JSON`, `Request(command, value) → JSON`,
`StateChanged(JSON)`. Hanya command dan nilai dari allowlist diterima. Service
berjalan sebagai user; aplikasi lain dalam sesi user yang sama dapat mengakses API.

## Bukti dan batas pengujian

Pemilik perangkat menguji CLI 0.1.0 pada CachyOS, Python 3.14.7, firmware
`TW230_20251017_v1.0.5`, channel SDP 1:
- Seluruh query `status --full` berhasil.
- Noise mode ANC memiliki readback `verified: true`.
- EQ Flat dan Bass terkirim, efek suara dilaporkan berhasil.

Build 0.3.0 menggunakan protokol yang sama. Tes otomatis meliputi framing,
checksum, EQ vectors, socket stream, konfigurasi, backend offline/partial state,
dan validasi request. Pengujian runtime GNOME Shell 50 dan hardware untuk build
extension ini masih harus dilakukan di laptop pengguna; tidak diklaim sudah lolos.

Referensi implementasi:
- https://gjs.guide/extensions/development/creating.html
- https://gjs.guide/extensions/topics/popup-menu.html
- https://gjs.guide/guides/gio/dbus.html
- https://gjs.guide/extensions/upgrading/gnome-shell-50.html

## Validasi popup

Tes JavaScript memeriksa gate koneksi (satu popup per reconnect), baterai unknown,
stagger animasi, pembersihan timer/signal/widget, reduced motion dan posisi monitor.
Lifecycle UI diuji dengan mock St/Clutter, bukan GNOME Shell asli. Tes Python
memakai GLib asli untuk worker dengan bus/device palsu. Tes integrasi D-Bus
dijalankan pada session bus terisolasi dengan perangkat palsu. Popup 0.3.0 masih
perlu diuji langsung pada GNOME Shell 50.5 di laptop pemilik perangkat.

Jalankan tes otomatis tanpa mengakses perangkat Bluetooth:

```bash
node --experimental-vm-modules --test tests/*.test.mjs
dbus-run-session -- /usr/bin/python3 -m unittest discover -s tests -v
```

## Lisensi

Kode asli proyek tersedia di bawah [MIT License](LICENSE),
Copyright (c) 2026 elamgah. Aset ilustrasi popup yang dihasilkan untuk proyek ini
disertakan di bawah lisensi yang sama sejauh hak yang dimiliki pembuatnya;
asal dan checksum aset tercatat di `extension/earfun@ell.local/assets/manifest.json`.

GNOME Shell menggunakan GPL-2.0-or-later. Distribusi extension sebagai karya
turunan GNOME Shell harus memenuhi ketentuan GPL yang kompatibel; lisensi MIT
pada kode asli proyek tidak menghapus kewajiban tersebut. Lihat
[pedoman lisensi GNOME](https://gjs.guide/extensions/review-guidelines/review-guidelines.html#licensing).

Proyek komunitas ini tidak berafiliasi dengan EarFun. Nama produk dan merek
EarFun tetap milik pemiliknya; lisensi proyek tidak memberikan hak atas merek tersebut.
