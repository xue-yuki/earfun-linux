# Protokol TW230 yang dipakai CLI

Sumber analisis: EarFun Audio 20.1.59, code 201. Base APK SHA-256 `86351a5009c69ac1844d700291a266672f0995b808fe343115c2f750455f104c`. Identitas model: `DeviceType.TW230` menghubungkan nama Air Pro 4i ke TW230Config, TW230ProtocolParser, TW230Equailzer.

Transport SPP berasal dari getter BaseProtocolParser yang diwarisi TW230/Earfun; DeviceManager memakai parser.getConnectType dan UUID perangkat saat memanggil BtEngine. SppConnect memakai socket RFCOMM. Channel belum diukur di hardware; CLI mencari melalui SDP.

Frame: `EF opcode[2] length[1] payload checksum[1] FE`. Checksum `(length + sum(payload)) & 255`, tanpa opcode. Formula dibandingkan dengan operasi sum byte Kotlin dari runtime upstream. Panjang frame adalah `length + 6`.

| Fitur | Baca | Tulis | Nilai payload |
| --- | --- | --- | --- |
| Versi | 1010 | — | String UTF-8; null padding dibuang |
| Baterai earbuds | 1014 | — | Byte kiri, kanan |
| Baterai casing | 1018 | — | Byte casing |
| Noise | 2080 | 2085 | 1 normal, 2 ambient, 3 ANC |
| Game | 2030 | 2035 | 1 off, 2 on |
| ANC level | 2310 | 2315 | 1 default/strong, 2 balanced, 3 wind, 4 adaptive |
| Spatial | 2190 | 2195 | 1 off, 2 on |
| Multipoint | 2140 | 2145 | 1 off, 2 on |
| EQ | Belum ditemukan | 2095 | Per-band payload, lihat di bawah |

Noise dan level ANC memakai override serta parser respons TW230, bukan pemetaan berbeda pada parser model lain. Setter dan respons boolean mode mengikuti EarfunProtocolParser. Status fitur belum diverifikasi over-the-air.

EQ per band: jumlah band (10), indeks 1..10, master gain int16 big-endian, frequency uint16 big-endian, gain int16 big-endian, Q uint16 big-endian. Frequency = int(Hz*3), gain = int(dB*60), Q = int(0.7*4096) = 2867. Master gain memakai lookup slider maksimum, mengikuti TW230Equailzer: -11 dB untuk indeks 0..16, kemudian -11.5, -12, -13, -14 dB untuk indeks 17..20. Seluruh gain dinyatakan oleh tabel nonuniform GAINS pada module protocol.py.

Contoh golden untuk EQ flat band pertama: `ef20950a0a01fd6c005e00000b331afe`. Band terakhir: `ef20950a0a0afd6cbb8000000b3300fe`. EQ -6 dB band pertama: `ef20950a0a01fd6c005efe980b33b0fe` (checksum b0 diverifikasi ulang dengan runtime Kotlin).

APK membedakan hardware string TW230/TW230_new berdasarkan firmware. Firmware pengguna belum diketahui. Hasil dekompilasi memiliki bridge-method/generic artefact; field opcode, encoding dan interpretasi respons dipakai sebagai fakta statis, bukan bukti perilaku seluruh firmware.

Query protocol tidak menyertakan request ID/nonce. Readback membuktikan nilai respons yang diterima setelah request, bukan bukti kausal atau persistensi. ACK/write EQ belum dipetakan; CLI tidak mengklaim EQ telah diterapkan hanya berdasarkan sendall.

Sinyal casing membuka/menutup belum ditemukan dan tidak disamakan dengan status koneksi/charging. CLI ini fokus controller; fase popup membutuhkan observasi advertisement perangkat.

Referensi runtime:
- https://docs.python.org/3/library/socket.html#socket-families
- https://github.com/bluez/bluez/blob/master/tools/sdptool.c
- https://www.myearfun.com/headphones/earfun-air-pro-4i-anc-true-wireless-earbuds-black
