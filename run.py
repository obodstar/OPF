import subprocess
import random
import time
import sys
import os
import threading
from datetime import datetime
from collections import defaultdict

# =============================================
#   versi kontrol  massal
# =============================================

WARNA = {
    "merah":    "\033[91m",
    "hijau":    "\033[92m",
    "kuning":   "\033[93m",
    "biru":     "\033[94m",
    "magenta":  "\033[95m",
    "cyan":     "\033[96m",
    "putih":    "\033[97m",
    "reset":    "\033[0m",
    "tebal":    "\033[1m",
    "redup":    "\033[2m",
}

def warna(teks, kode):
    return f"{WARNA.get(kode, '')}{teks}{WARNA['reset']}"

def header():
    os.system("cls" if os.name == "nt" else "clear")
    print(warna("═" * 58, "cyan"))
    print(warna("                      📱  OPF", "tebal"))
    print(warna("                   Dibuat oleh Obar    ", "redup"))
    print(warna("═" * 58, "cyan"))
    print()

# ─── LOCK ────────────────────────────────────────────────────
print_lock = threading.Lock()
log_lock   = threading.Lock()

# ─── LOGGER ──────────────────────────────────────────────────

LOG_FILE = "log.txt"

def tulis_log(pesan, tipe="INFO"):
    """Tulis log ke file log.txt secara thread-safe."""
    waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baris = f"[{waktu}] [{tipe.upper():7}] {pesan}\n"
    with log_lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(baris)

def log(pesan, tipe="info"):
    """Tampilkan log ke terminal + tulis ke file."""
    waktu = datetime.now().strftime("%H:%M:%S")
    ikon = {
        "info":    "ℹ️ ",
        "sukses":  "✅",
        "error":   "❌",
        "proses":  "⏳",
        "warning": "⚠️ ",
        "stat":    "📊",
        "log":     "📝",
    }
    warna_map = {
        "info":    "putih",
        "sukses":  "hijau",
        "error":   "merah",
        "proses":  "kuning",
        "warning": "kuning",
        "stat":    "cyan",
        "log":     "redup",
    }
    with print_lock:
        print(f"  [{warna(waktu, 'cyan')}] {ikon.get(tipe,'  ')} {warna(pesan, warna_map.get(tipe,'putih'))}")
    tulis_log(pesan, tipe)

# ─── ADB HELPERS ─────────────────────────────────────────────

def jalankan_adb(perintah, device_id=None):
    base = ["adb"]
    if device_id:
        base += ["-s", device_id]
    hasil = subprocess.run(base + perintah, capture_output=True, text=True)
    return hasil.stdout.strip(), hasil.stderr.strip()

def get_daftar_device():
    out, _ = jalankan_adb(["devices"])
    baris = out.splitlines()[1:]
    devices = []
    for b in baris:
        if "\tdevice" in b:
            devices.append(b.split("\t")[0].strip())
    return devices

def buka_url_di_device(device_id, url):
    perintah = [
        "shell", "am", "start",
        "-a", "android.intent.action.VIEW",
        "-d", url,
        "com.android.chrome"
    ]
    _, err = jalankan_adb(perintah, device_id)
    return "Error" not in err

def paksa_putar_video(device_id):
    jalankan_adb(["shell", "input", "tap", "540", "960"], device_id)
    time.sleep(0.5)

def scroll_halaman(device_id):
    jalankan_adb(["shell", "input", "swipe", "540", "900", "540", "400", "800"], device_id)

def kembali_ke_home(device_id):
    jalankan_adb(["shell", "input", "keyevent", "KEYCODE_HOME"], device_id)

def get_model_device(device_id):
    model, _ = jalankan_adb(["shell", "getprop", "ro.product.model"], device_id)
    return model or "Unknown"

def get_baterai_device(device_id):
    battery, _ = jalankan_adb(["shell", "dumpsys", "battery"], device_id)
    if battery:
        for baris in battery.splitlines():
            if "level" in baris:
                return baris.split(":")[-1].strip() + "%"
    return "?"

# ─── BACA LINK ───────────────────────────────────────────────

def baca_link(nama_file="listlink.txt"):
    if not os.path.exists(nama_file):
        log(f"File '{nama_file}' tidak ditemukan!", "error")
        return []
    links = []
    with open(nama_file, "r", encoding="utf-8") as f:
        for baris in f:
            baris = baris.strip()
            if baris and not baris.startswith("#"):
                links.append(baris)
    return links

# ─── ANTRIAN LINK PER DEVICE (ANTI-DOUBLE) ───────────────────

class AntrianDevice:
    """
    Setiap device punya antrian link acak sendiri.
    Link tidak akan diulang sampai semua link sudah dikunjungi.
    Setelah semua habis, antrian dikocok ulang otomatis.
    """
    def __init__(self, device_id, nomor, links):
        self.device_id  = device_id
        self.nomor      = nomor
        self.nama       = f"HP#{nomor}(...{device_id[-6:]})"
        self.semua_link = links.copy()
        self.antrian    = []
        self.riwayat    = []   # semua link yang sudah dikunjungi (global)
        self._isi_antrian()

    def _isi_antrian(self):
        """Kocok semua link dan masukkan ke antrian."""
        acak = self.semua_link.copy()
        random.shuffle(acak)
        # Pastikan link pertama antrian baru ≠ link terakhir yang dikunjungi
        if self.riwayat and len(acak) > 1:
            while acak[0] == self.riwayat[-1]:
                random.shuffle(acak)
        self.antrian = acak

    def ambil_link_berikutnya(self):
        """Ambil link berikutnya dari antrian. Auto-refill jika habis."""
        if not self.antrian:
            self._isi_antrian()
        link = self.antrian.pop(0)
        self.riwayat.append(link)
        return link

    def sisa_antrian(self):
        return len(self.antrian)

# ─── STATISTIK ───────────────────────────────────────────────

class Statistik:
    def __init__(self):
        self.lock          = threading.Lock()
        self.total_sukses  = 0
        self.total_gagal   = 0
        self.per_device    = defaultdict(lambda: {"sukses": 0, "gagal": 0})
        self.per_link      = defaultdict(lambda: {"sukses": 0, "gagal": 0})
        self.waktu_mulai   = datetime.now()

    def catat(self, device_nama, link, sukses):
        with self.lock:
            if sukses:
                self.total_sukses += 1
                self.per_device[device_nama]["sukses"] += 1
                self.per_link[link]["sukses"] += 1
            else:
                self.total_gagal += 1
                self.per_device[device_nama]["gagal"] += 1
                self.per_link[link]["gagal"] += 1

    def tampilkan_ringkasan(self):
        durasi = datetime.now() - self.waktu_mulai
        jam    = int(durasi.total_seconds()) // 3600
        menit  = (int(durasi.total_seconds()) % 3600) // 60
        detik  = int(durasi.total_seconds()) % 60

        print()
        print(warna("  ╔══════════════════════════════════════════════╗", "magenta"))
        print(warna("  ║          📊  RINGKASAN STATISTIK             ║", "magenta"))
        print(warna("  ╠══════════════════════════════════════════════╣", "magenta"))
        print(f"  ║  Total kunjungan sukses : {warna(str(self.total_sukses).ljust(5), 'hijau')}                  ║")
        print(f"  ║  Total kunjungan gagal  : {warna(str(self.total_gagal).ljust(5), 'merah')}                  ║")
        print(f"  ║  Durasi berjalan        : {warna(f'{jam:02d}:{menit:02d}:{detik:02d}', 'cyan')}               ║")
        print(warna("  ╠══════════════════════════════════════════════╣", "magenta"))
        print(warna("  ║  Per Device:                                 ║", "magenta"))
        for nama, data in self.per_device.items():
            baris = f"  {nama}: ✅{data['sukses']} ❌{data['gagal']}"
            print(f"  ║  {baris.ljust(44)}║")
        print(warna("  ╠══════════════════════════════════════════════╣", "magenta"))
        print(warna("  ║  Per Link:                                   ║", "magenta"))
        for link, data in self.per_link.items():
            pendek = (link[-38:] + "..") if len(link) > 40 else link
            baris  = f"  ✅{data['sukses']} ❌{data['gagal']} — {pendek}"
            print(f"  ║  {baris.ljust(44)}║")
        print(warna("  ╚══════════════════════════════════════════════╝", "magenta"))

        # Tulis ringkasan ke log juga
        tulis_log("=" * 50, "STAT")
        tulis_log(f"RINGKASAN — Sukses: {self.total_sukses} | Gagal: {self.total_gagal} | Durasi: {jam:02d}:{menit:02d}:{detik:02d}", "STAT")
        for nama, data in self.per_device.items():
            tulis_log(f"  {nama} → sukses:{data['sukses']} gagal:{data['gagal']}", "STAT")
        for link, data in self.per_link.items():
            tulis_log(f"  {link} → sukses:{data['sukses']} gagal:{data['gagal']}", "STAT")
        tulis_log("=" * 50, "STAT")

# ─── TUGAS PER DEVICE (THREAD) ───────────────────────────────

def tugas_device(antrian, link, durasi_detik, hasil_dict, statistik, putaran, sesi):
    """Dijalankan paralel. Setiap device dapat link unik dari antriannya sendiri."""
    nama = antrian.nama
    try:
        tulis_log(f"MULAI | {nama} | Putaran:{putaran} Sesi:{sesi} | {link}", "PROSES")

        sukses = buka_url_di_device(antrian.device_id, link)
        if not sukses:
            log(f"{nama} → GAGAL buka: {link}", "error")
            hasil_dict[antrian.device_id] = False
            statistik.catat(nama, link, False)
            tulis_log(f"GAGAL | {nama} | {link}", "ERROR")
            return

        log(f"{nama} → {link}", "sukses")
        tulis_log(f"BUKA  | {nama} | {link}", "SUKSES")

        time.sleep(3)
        paksa_putar_video(antrian.device_id)
        time.sleep(0.5)
        scroll_halaman(antrian.device_id)

        time.sleep(max(0, durasi_detik - 3.5))

        kembali_ke_home(antrian.device_id)

        hasil_dict[antrian.device_id] = True
        statistik.catat(nama, link, True)
        tulis_log(f"DONE  | {nama} | {link}", "SUKSES")

    except Exception as e:
        log(f"{nama} → ERROR: {e}", "error")
        tulis_log(f"ERROR | {nama} | {link} | {e}", "ERROR")
        hasil_dict[antrian.device_id] = False
        statistik.catat(nama, link, False)

# ─── MENU 1: JALANKAN PROGRAM ────────────────────────────────

def jalankan_program():
    header()
    print(warna("  ▶  MENU 1 — JALANKAN PROGRAM TESTING", "tebal"))
    print()

    log("Mendeteksi device yang terhubung...", "proses")
    devices = get_daftar_device()

    if not devices:
        log("Tidak ada device ADB yang terdeteksi!", "error")
        log("Pastikan USB Debugging aktif & kabel terhubung.", "warning")
        input("\n  Tekan Enter untuk kembali ke menu...")
        return

    log(f"Ditemukan {len(devices)} device:", "sukses")
    for i, d in enumerate(devices, 1):
        print(f"      [{i}] {warna(d, 'cyan')}")
    print()

    log("Membaca daftar link dari listlink.txt...", "proses")
    links = baca_link("listlink.txt")

    if not links:
        log("Tidak ada link yang valid di listlink.txt!", "error")
        input("\n  Tekan Enter untuk kembali ke menu...")
        return

    log(f"Ditemukan {len(links)} link video.", "sukses")
    print()

    # Input durasi
    while True:
        try:
            durasi_menit = float(input(warna("  ⏱  Berapa lama tiap link diputar? (menit, contoh: 3): ", "kuning")))
            if durasi_menit <= 0:
                raise ValueError
            break
        except ValueError:
            log("Masukkan angka lebih dari 0.", "error")

    # Input jumlah putaran
    while True:
        try:
            jumlah_putaran = int(input(warna("  🔁  Berapa kali putaran? (0 = tak terbatas): ", "kuning")))
            if jumlah_putaran < 0:
                raise ValueError
            break
        except ValueError:
            log("Masukkan angka 0 atau lebih.", "error")

    durasi_detik  = durasi_menit * 60
    tak_terbatas  = jumlah_putaran == 0

    print()
    print(warna("  ─" * 29, "biru"))
    log(f"Device aktif    : {len(devices)} HP", "info")
    log(f"Total link      : {len(links)}", "info")
    log(f"Durasi per link : {durasi_menit} menit", "info")
    log(f"Mode link       : Anti-double per device + Paralel serentak", "info")
    log(f"Log file        : {LOG_FILE}", "info")
    log(f"Jumlah putaran  : {'Tak terbatas ♾' if tak_terbatas else jumlah_putaran}", "info")
    print(warna("  ─" * 29, "biru"))
    print()

    konfirmasi = input(warna("  Mulai sekarang? (y/n): ", "hijau")).strip().lower()
    if konfirmasi != "y":
        log("Dibatalkan.", "warning")
        input("\n  Tekan Enter untuk kembali ke menu...")
        return

    # Inisialisasi antrian per device
    antrian_devices = []
    for i, dev in enumerate(devices, 1):
        antrian_devices.append(AntrianDevice(dev, i, links))

    # Inisialisasi statistik
    statistik = Statistik()

    # Header log file
    tulis_log("=" * 60, "INFO")
    tulis_log(f"SESI DIMULAI — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO")
    tulis_log(f"Device: {len(devices)} | Link: {len(links)} | Durasi: {durasi_menit} menit", "INFO")
    tulis_log("=" * 60, "INFO")

    print()
    log("Program dimulai! Tekan Ctrl+C untuk berhenti.", "sukses")
    log(f"Log disimpan di: {warna(LOG_FILE, 'cyan')}", "log")
    print()

    putaran = 0

    try:
        while tak_terbatas or putaran < jumlah_putaran:
            putaran += 1

            print(warna(f"\n  ═══ PUTARAN KE-{putaran} {'(♾)' if tak_terbatas else f'/{jumlah_putaran}'} ═══", "magenta"))
            tulis_log(f"PUTARAN {putaran} DIMULAI", "INFO")
            print()

            # Jumlah sesi per putaran = jumlah link
            # Sehingga setiap link dikunjungi minimal sekali per putaran per device
            jumlah_sesi = len(links)

            for sesi in range(jumlah_sesi):
                print(warna(f"  ── Sesi {sesi+1}/{jumlah_sesi} ──", "biru"))

                # Ambil link berikutnya dari antrian masing-masing device (anti-double)
                penugasan = {}
                for antrian in antrian_devices:
                    penugasan[antrian.device_id] = antrian.ambil_link_berikutnya()

                # Tampilkan penugasan sesi ini
                for antrian in antrian_devices:
                    link = penugasan[antrian.device_id]
                    sisa = antrian.sisa_antrian()
                    print(f"    {warna(antrian.nama, 'putih')} → {warna(link, 'cyan')} {warna(f'(sisa antrian: {sisa})', 'redup')}")
                print()

                # Jalankan semua device SERENTAK dengan threading
                hasil_dict = {}
                threads    = []

                for antrian in antrian_devices:
                    t = threading.Thread(
                        target=tugas_device,
                        args=(
                            antrian,
                            penugasan[antrian.device_id],
                            durasi_detik,
                            hasil_dict,
                            statistik,
                            putaran,
                            sesi + 1
                        ),
                        daemon=True
                    )
                    threads.append(t)

                log(f"Membuka {len(devices)} HP secara SERENTAK...", "proses")

                # Start semua thread serentak
                for t in threads:
                    t.start()

                # Countdown
                waktu_mulai = time.time()
                while any(t.is_alive() for t in threads):
                    berlalu = time.time() - waktu_mulai
                    sisa    = max(0, durasi_detik - berlalu)
                    m, s    = int(sisa) // 60, int(sisa) % 60
                    with print_lock:
                        print(
                            f"\r    ⏳ {len(devices)} HP menonton serentak... "
                            f"sisa: {warna(f'{m:02d}:{s:02d}', 'kuning')}  "
                            f"| ✅{statistik.total_sukses} ❌{statistik.total_gagal}  ",
                            end="", flush=True
                        )
                    time.sleep(1)

                for t in threads:
                    t.join()

                print(f"\r    ✅ Sesi {sesi+1} selesai!{' ' * 50}")

                sukses_sesi = sum(1 for v in hasil_dict.values() if v)
                log(
                    f"Sesi {sesi+1}: {sukses_sesi}/{len(devices)} HP sukses "
                    f"| Total: ✅{statistik.total_sukses} ❌{statistik.total_gagal}",
                    "stat"
                )
                print()

            tulis_log(f"PUTARAN {putaran} SELESAI", "INFO")
            log(f"Putaran {putaran} selesai.", "sukses")

    except KeyboardInterrupt:
        print()
        print()
        log("Program dihentikan oleh pengguna.", "warning")

    finally:
        statistik.tampilkan_ringkasan()
        tulis_log("SESI BERAKHIR", "INFO")
        input("\n  Tekan Enter untuk kembali ke menu...")

# ─── MENU 2: KELOLA LINK ─────────────────────────────────────

def kelola_link():
    header()
    print(warna("  📋  MENU 2 — KELOLA DAFTAR LINK", "tebal"))
    print()

    links = baca_link("listlink.txt")
    log(f"Total link saat ini: {len(links)}", "info")
    print()

    if links:
        print(warna("  Daftar link:", "kuning"))
        for i, l in enumerate(links, 1):
            print(f"    {warna(str(i).rjust(3), 'cyan')}. {l}")
        print()

    print("  Pilihan:")
    print("    [1] Tambah link baru")
    print("    [2] Hapus link")
    print("    [3] Kembali")
    print()

    pilihan = input(warna("  Pilih: ", "kuning")).strip()

    if pilihan == "1":
        link_baru = input("  Masukkan URL baru: ").strip()
        if link_baru.startswith("http"):
            links.append(link_baru)
            with open("listlink.txt", "w", encoding="utf-8") as f:
                f.write("# Daftar Link Video Website Anda\n")
                for l in links:
                    f.write(l + "\n")
            log("Link berhasil ditambahkan!", "sukses")
        else:
            log("URL tidak valid (harus diawali http/https).", "error")

    elif pilihan == "2":
        try:
            no = int(input("  Nomor link yang ingin dihapus: ")) - 1
            if 0 <= no < len(links):
                dihapus = links.pop(no)
                with open("listlink.txt", "w", encoding="utf-8") as f:
                    f.write("# Daftar Link Video Website Anda\n")
                    for l in links:
                        f.write(l + "\n")
                log(f"Link '{dihapus}' dihapus.", "sukses")
            else:
                log("Nomor tidak valid.", "error")
        except ValueError:
            log("Masukkan angka.", "error")

    input("\n  Tekan Enter untuk kembali ke menu...")

# ─── MENU 3: CEK STATUS DEVICE ───────────────────────────────

def cek_device():
    header()
    print(warna("  📱  MENU 3 — STATUS DEVICE ADB", "tebal"))
    print()
    log("Mengecek semua device yang terhubung...", "proses")
    print()

    devices = get_daftar_device()

    if not devices:
        log("Tidak ada device yang terdeteksi.", "error")
        print()
        print("  Tips:")
        print("    • Aktifkan USB Debugging di Pengaturan → Developer Options")
        print("    • Jalankan: adb kill-server && adb start-server")
        print("    • Coba cabut dan pasang ulang kabel USB")
    else:
        log(f"Total device terhubung: {len(devices)}", "sukses")
        print()
        print(warna("  ┌──────────────────────────────────────────────┐", "biru"))
        for i, d in enumerate(devices, 1):
            model  = get_model_device(d)
            batt   = get_baterai_device(d)
            print(f"  │  [{warna(str(i), 'kuning')}] {warna(d, 'cyan')}")
            print(f"  │      Model   : {warna(model, 'putih')}")
            print(f"  │      Baterai : {warna(batt, 'hijau')}")
            print(warna("  │", "biru"))
        print(warna("  └──────────────────────────────────────────────┘", "biru"))

    input("\n  Tekan Enter untuk kembali ke menu...")

# ─── MENU 4: LIHAT LOG ───────────────────────────────────────

def lihat_log():
    header()
    print(warna("  📝  MENU 4 — LIHAT LOG TERAKHIR", "tebal"))
    print()

    if not os.path.exists(LOG_FILE):
        log("Belum ada file log. Jalankan program dulu.", "warning")
        input("\n  Tekan Enter untuk kembali ke menu...")
        return

    # Tampilkan 40 baris terakhir
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        semua = f.readlines()

    tampil = semua[-40:] if len(semua) > 40 else semua
    ukuran = os.path.getsize(LOG_FILE) / 1024

    log(f"File: {LOG_FILE} ({ukuran:.1f} KB) — menampilkan {len(tampil)} baris terakhir", "info")
    print()
    print(warna("  ┌" + "─" * 52 + "┐", "redup"))
    for baris in tampil:
        teks = baris.rstrip()
        if "SUKSES" in teks:
            cetak = warna(teks[:54], "hijau")
        elif "ERROR" in teks or "GAGAL" in teks:
            cetak = warna(teks[:54], "merah")
        elif "STAT" in teks:
            cetak = warna(teks[:54], "cyan")
        else:
            cetak = warna(teks[:54], "redup")
        print(f"  │ {cetak}")
    print(warna("  └" + "─" * 52 + "┘", "redup"))
    print()

    hapus = input(warna("  Hapus log sekarang? (y/n): ", "kuning")).strip().lower()
    if hapus == "y":
        os.remove(LOG_FILE)
        log("Log dihapus.", "sukses")

    input("\n  Tekan Enter untuk kembali ke menu...")

# ─── MENU UTAMA ──────────────────────────────────────────────

def menu_utama():
    while True:
        header()
        links   = baca_link("listlink.txt")
        devices = get_daftar_device()
        ada_log = os.path.exists(LOG_FILE)

        print(f"  Status : {warna(str(len(devices)), 'hijau')} device  │  "
              f"{warna(str(len(links)), 'cyan')} link  │  "
              f"Log: {warna('Ada ✓', 'hijau') if ada_log else warna('Kosong', 'redup')}")
        print()
        print(warna("  ╔══════════════════════════════════════════╗", "biru"))
        print(warna("  ║              MENU                        ║", "biru"))
        print(warna("  ╠══════════════════════════════════════════╣", "biru"))
        print(warna("  ║  [1] ▶  Jalankan Program Testing         ║", "putih"))
        print(warna("  ║  [2] 📋  Kelola Daftar Link              ║", "putih"))
        print(warna("  ║  [3] 📱  Cek Status Device               ║", "putih"))
        print(warna("  ║  [4] 📝  Lihat Log Terakhir              ║", "putih"))
        print(warna("  ║  [5] ❌  Keluar                          ║", "putih"))
        print(warna("  ╚══════════════════════════════════════════╝", "biru"))
        print()

        pilihan = input(warna("  Pilih menu [1-5]: ", "kuning")).strip()

        if pilihan == "1":
            jalankan_program()
        elif pilihan == "2":
            kelola_link()
        elif pilihan == "3":
            cek_device()
        elif pilihan == "4":
            lihat_log()
        elif pilihan == "5":
            print()
            log("Sampai jumpa! 👋", "sukses")
            print()
            sys.exit(0)
        else:
            log("Pilihan tidak valid.", "error")
            time.sleep(1)

# ─── ENTRY POINT ─────────────────────────────────────────────

if __name__ == "__main__":
    menu_utama()
