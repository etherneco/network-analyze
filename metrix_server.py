#!/usr/bin/env python3
import threading
import os
import sys
import socket
import platform
import subprocess
import time
import io
import logging
import requests

import config

# Biblioteki Flask i systemowe
from flask import Flask, jsonify, request, send_file
import psutil

# Biblioteki graficzne i System Tray
try:
    import mss
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    # Jeśli brak bibliotek graficznych, screenshoty nie będą działać
    mss = None
    Image = ImageDraw = ImageFont = None
try:
    import pystray
    from pystray import MenuItem as item
except ImportError:
    # Brak pystray wyłącza ikonę, ale nie screenshoty
    pystray = None
    item = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import keyboard  # cross-platform hotkey lib
except ImportError:
    keyboard = None


# Import ctypes tylko na Windows
if platform.system() == "Windows":
    import ctypes
    from ctypes import wintypes
    try:
        user32 = ctypes.windll.user32
    except Exception:
        user32 = None
else:
    user32 = None

# --- KONFIGURACJA ---
app = Flask(__name__)
system = platform.system()
is_windows = system == "Windows"

# Obsługa argumentu (np. python metrix_server.py ENOCH)
if len(sys.argv) > 1:
    hostname = sys.argv[1]
else:
    hostname = socket.gethostname()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMMANDS_DIR = os.path.join(BASE_DIR, "command")
COMMANDS_FILE = os.path.join(COMMANDS_DIR, f"{hostname}.txt")

# Wyłączamy logi konsolowe Flaska i ustawiamy bazowy poziom logów
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ==========================================
# MAGIA: UKRYWANIE KONSOLI (WINDOWS)
# ==========================================
def hide_console():
    """
    Jeśli jesteśmy na Windowsie, znajdujemy okno konsoli tego procesu i je ukrywamy.
    """
    if is_windows:
        try:
            # Pobieramy uchwyt do bieżącego okna konsoli
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd != 0:
                # 0 = SW_HIDE (Ukryj), 5 = SW_SHOW (Pokaż)
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass

# ==========================================
# LOGIKA SERWERA
# ==========================================

def get_window_rect_by_pid(target_pid):
    if not is_windows: return None
    try:
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        found_rect = []
        def enum_windows_callback(hwnd, _):
            if not user32.IsWindowVisible(hwnd): return True
            lpdw_process_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_process_id))
            if lpdw_process_id.value == target_pid:
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 0 and h > 0:
                    found_rect.append({"top": rect.top, "left": rect.left, "width": w, "height": h})
                    return False
            return True
        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return found_rect[0] if found_rect else None
    except: return None

def generate_fallback_image(pid, proc_name, reason="Info"):
    if not Image or not ImageDraw:
        return None
    width, height = 300, 160
    img = Image.new('RGB', (width, height), color=(30, 30, 40))
    d = ImageDraw.Draw(img)
    try: font_large = ImageFont.truetype("arial.ttf", 20); font_small = ImageFont.truetype("arial.ttf", 14)
    except: font_large = ImageFont.load_default(); font_small = ImageFont.load_default()
    d.rectangle([0, 0, width-1, height-1], outline=(42, 108, 255), width=3)
    d.text((15, 20), f"HOST: {hostname}", font=font_small, fill=(150, 150, 150))
    d.text((15, 50), f"{proc_name}", font=font_large, fill=(255, 255, 255))
    d.text((15, 80), f"PID: {pid}", font=font_large, fill=(200, 200, 200))
    d.text((15, 120), f"[{reason}]", font=font_small, fill=(255, 100, 100))
    img_io = io.BytesIO()
    img.save(img_io, 'JPEG', quality=80)
    img_io.seek(0)
    return img_io

def get_metrics():
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_count = psutil.cpu_count(logical=True)
    mem = psutil.virtual_memory()
    swp = psutil.swap_memory()
    disks = {}
    try:
        for part in psutil.disk_partitions(all=False):
            if is_windows and ("cdrom" in part.opts or part.fstype == ""): continue
            u = psutil.disk_usage(part.mountpoint)
            disks[part.mountpoint] = {"total": u.total, "used": u.used, "free": u.free, "percent": u.percent}
    except: pass
    
    procs = []
    try:
        for p in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                mem_usage = p.info['memory_info'].rss
                procs.append({"pid": p.info['pid'], "name": p.info['name'], "mem": mem_usage})
            except: pass
    except: pass
    procs_sorted = sorted(procs, key=lambda x: x['mem'], reverse=True)[:30]

    return {
        "timestamp": int(time.time()),
        "host": hostname,
        "cpu": {"usage_percent": cpu_percent, "cores": cpu_count},
        "memory": {"total": mem.total, "used": mem.used, "percent": mem.percent},
        "swap": {"total": swp.total, "used": swp.used, "percent": swp.percent},
        "disks": disks,
        "processes": procs_sorted
    }

# --- ENDPOINTS FLASK ---
@app.route("/metrics")
def metrics(): return jsonify(get_metrics())

@app.route("/screenshot/<int:pid>")
def screenshot_pid(pid):
    if not mss or not Image:
        return jsonify({"error": "screenshot_unavailable"}), 503
    proc_name = "Unknown"
    try: proc_name = psutil.Process(pid).name()
    except: pass
    rect = get_window_rect_by_pid(pid)
    if rect:
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[0]
                if rect['left'] < monitor['left']: rect['left'] = monitor['left']
                if rect['top'] < monitor['top']: rect['top'] = monitor['top']
                sct_img = sct.grab(rect)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                img.thumbnail((400, 300))
                img_io = io.BytesIO()
                img.save(img_io, 'JPEG', quality=70)
                img_io.seek(0)
                return send_file(img_io, mimetype='image/jpeg')
        except: pass
    reason = "Running" if not is_windows else "Background"
    fallback = generate_fallback_image(pid, proc_name, reason)
    if fallback:
        return send_file(fallback, mimetype='image/jpeg')
    return jsonify({"error": "screenshot_unavailable"}), 503

@app.route("/screenshot/full")
def screenshot_full():
    if not mss or not Image or not ImageDraw:
        return jsonify({"error": "screenshot_unavailable"}), 503

    def get_cursor_pos():
        if is_windows and user32:
            pt = wintypes.POINT()
            if user32.GetCursorPos(ctypes.byref(pt)):
                return pt.x, pt.y
        try:
            import pyautogui
            p = pyautogui.position()
            return p.x, p.y
        except Exception:
            return None

    try:
        with mss.mss() as sct:
            cursor = get_cursor_pos()
            monitors = sct.monitors
            monitor = monitors[1] if len(monitors) > 1 else monitors[0]
            if cursor:
                cx, cy = cursor
                for m in monitors[1:] or monitors:
                    if m["left"] <= cx < m["left"] + m["width"] and m["top"] <= cy < m["top"] + m["height"]:
                        monitor = m
                        break

            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            if cursor:
                cx, cy = cursor
                rel_x = cx - monitor["left"]
                rel_y = cy - monitor["top"]
                d = ImageDraw.Draw(img)
                r = 12
                d.ellipse((rel_x - r, rel_y - r, rel_x + r, rel_y + r), fill=(255, 0, 0))

            img = img.resize((800, int(img.size[1]*(800/img.size[0]))), Image.Resampling.LANCZOS)
            img_io = io.BytesIO()
            img.save(img_io, 'JPEG', quality=65)
            img_io.seek(0)
            return send_file(img_io, mimetype='image/jpeg')
    except:
        fallback = generate_fallback_image(0, "Error", "No Display")
        if fallback:
            return send_file(fallback, mimetype='image/jpeg')
        return jsonify({"error": "screenshot_unavailable"}), 503

def parse_commands_file():
    cmd_list = []
    if not os.path.exists(COMMANDS_FILE): return cmd_list
    try:
        with open(COMMANDS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    l, c = line.split("=", 1)
                    cmd_list.append({"label": l.strip(), "cmd": c.strip().strip('"\'')})
    except: pass
    return cmd_list

@app.route("/command_list")
def command_list(): return jsonify({hostname: parse_commands_file()})

@app.route("/command", methods=["POST"])
def command():
    if not request.is_json: return jsonify({"error": "JSON"}), 400
    data = request.get_json(); cmd = data.get("cmd", "")
    if is_windows: subprocess.Popen(cmd, shell=True, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    else: subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
    return jsonify({"status": "started"}), 202

@app.route("/kill/<int:pid>", methods=["POST"])
def kill(pid):
    try: os.kill(pid, 9); return jsonify({"status": "killed"})
    except Exception as e: return jsonify({"error": str(e)})

@app.route("/clipboard", methods=["GET"])
def clipboard():
    if not pyperclip:
        return jsonify({"error": "clipboard_unavailable"}), 500
    try:
        text = pyperclip.paste()
        if isinstance(text, str) and text:
            size = len(text.encode("utf-8"))
            return jsonify({
                "type": "text",
                "encoding": "plain" if size < 64_000 else "stream",
                "size": size,
                "data": text if size < 64_000 else None
            })
    except Exception as e:
        logging.warning(f"Clipboard read failed: {e}")

    return jsonify({
        "type": "unknown",
        "encoding": "plain",
        "size": 0,
        "data": ""
    })

@app.route("/clipboard", methods=["POST"])
def set_clipboard():
    if not pyperclip:
        return jsonify({"error": "clipboard_unavailable"}), 500

    if not request.is_json:
        return jsonify({"error": "json_required"}), 400

    data = request.get_json(silent=True) or {}
    text = data.get("clipboard", "")

    if not isinstance(text, str):
        return jsonify({"error": "clipboard_must_be_text"}), 400

    try:
        pyperclip.copy(text)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/clipboard/stream")
def clipboard_stream():
    if not pyperclip:
        return jsonify({"error": "clipboard_unavailable"}), 500
    text = pyperclip.paste() or ""

    def gen():
        for i in range(0, len(text), 4096):
            yield text[i:i+4096]

    return app.response_class(gen(), mimetype="text/plain")


# ==========================================
# HOTKEY: CTRL+WIN+ALT+T -> BARRIER SNAPSHOT
# ==========================================

WM_HOTKEY = 0x0312


def handle_barrier_hotkey():
    """
    Fetch current Barrier screen info and send minimal context to analyzer.
    Triggered by the global hotkey.
    """
    if not config.BARRIER_STATE_URL or not config.ANALYZER_URL:
        logging.warning("Hotkey ignored: BARRIER_STATE_URL or ANALYZER_URL not set")
        return
    data = None
    last_err = None
    for attempt in range(1, 11):  # próbujemy do 10 razy
        try:
            r = requests.get(config.BARRIER_STATE_URL, timeout=config.BARRIER_REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            break
        except requests.exceptions.RequestException as e:
            last_err = e
            logging.warning("Barrier state unreachable (try %s/10): %s", attempt, e)
            time.sleep(0.5)
        except Exception as e:
            logging.error("Barrier state error (try %s/10): %s", attempt, e)
            return

    if data is None:
        logging.error("Barrier state failed after retries: %s", last_err)
        return

    server = data.get("server", {}) if isinstance(data, dict) else {}
    screen = server.get("current")
    screen_ip = server.get("ip")

    if not screen or not screen_ip:
        logging.error("Invalid barrier payload: %s", data)
        return

    payload = {
        "screen_name": screen,
        "ip_actual_screen": screen_ip,
    }

    try:
        requests.post(
            config.ANALYZER_URL,
            json=payload,
            timeout=config.ANALYZER_REQUEST_TIMEOUT,
        )
        logging.info("Analyzer notified for screen %s (%s)", screen, screen_ip)
    except Exception as e:
        logging.error("Analyzer error: %s", e)


def hotkey_listener():
    """
    Register and listen for Ctrl+Win+Alt+T (Windows/Linux) or Ctrl+Cmd+Alt+T (macOS).
    Windows uses WinAPI for reliability; other platforms use the optional `keyboard` lib.
    """
    # --- Windows path (WinAPI, no external deps) ---
    if is_windows and user32:
        MOD_ALT = 0x0001
        MOD_CONTROL = 0x0002
        MOD_WIN = 0x0008
        VK_T = 0x54
        HOTKEY_ID = 1

        if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_ALT | MOD_CONTROL | MOD_WIN, VK_T):
            logging.warning("RegisterHotKey failed for Ctrl+Win+Alt+T")
            return

        msg = wintypes.MSG()
        try:
            while True:
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res == 0:
                    break  # WM_QUIT
                if res == -1:
                    logging.error("GetMessageW failed for hotkey listener")
                    break
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    try:
                        handle_barrier_hotkey()
                    except KeyboardInterrupt:
                        logging.info("Hotkey handler interrupted")
                        break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID)
        return

    # --- Linux/macOS path using keyboard ---
    if not keyboard:
        logging.warning("Hotkey ignored: keyboard module not installed")
        return

    if system == "Darwin":
        combos = ["ctrl+alt+cmd+t"]
    else:
        combos = [
            "ctrl+alt+t",            # minimal fallback
            "ctrl+alt+windows+t",
            "ctrl+alt+win+t",
        ]

    def on_hotkey(combo_name: str):
        logging.info("Hotkey triggered: %s", combo_name)
        handle_barrier_hotkey()
    try:
        registered = []
        for combo in combos:
            logging.info("Trying to register hotkey: %s", combo)
            try:
                keyboard.add_hotkey(
                    combo,
                    lambda c=combo: on_hotkey(c),
                    suppress=True,
                    trigger_on_release=False
                )
                registered.append(combo)
            except Exception as e:
                logging.warning("Hotkey register failed for %s: %s", combo, e)

        if not registered:
            logging.warning("No hotkey registered (keyboard module loaded but hooks failed)")
            return

        logging.info("Hotkey registered: %s", ", ".join(registered))
        # blokujemy się, aby hook pozostał aktywny; gdy coś padnie, pętla się przerwie
        while True:
            keyboard.wait(hotkey=None)
    except KeyboardInterrupt:
        logging.info("Hotkey listener interrupted")
    except Exception as e:
        logging.error("Hotkey listener error: %s", e)
    finally:
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass


@app.route("/hotkey", methods=["POST", "GET"])
def hotkey_http_trigger():
    """
    HTTP trigger for the Barrier->Analyzer action.
    Użyteczne, gdy systemowy globalny hotkey nie działa (np. Wayland):
    przypisz własny skrót do `curl http://127.0.0.1:28000/hotkey`.
    """
    try:
        handle_barrier_hotkey()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==========================================
# SYSTEM TRAY + MAIN
# ==========================================

def create_tray_icon():
    if not Image or not ImageDraw:
        return None
    width = 64; height = 64; color1 = (0, 0, 0); color2 = (42, 108, 255)
    image = Image.new('RGB', (width, height), color1)
    d = ImageDraw.Draw(image)
    d.rectangle([10, 10, 54, 54], fill=color2)
    return image

def run_flask_thread():
    app.run(
        host=config.METRIX_SERVER_HOST,
        port=config.METRIX_SERVER_PORT,
        threaded=True,
        debug=False,
        use_reloader=False,
    )

def on_quit(icon, item):
    icon.stop()
    os._exit(0)

if __name__ == "__main__":
    try:
        # 1. UKRYWAMY OKNO JEŚLI WINDOWS (Teraz funkcja jest zdefiniowana!)
        hide_console()
        
        # Init
        psutil.cpu_percent(interval=None)
        if not os.path.exists(COMMANDS_DIR):
            try: os.makedirs(COMMANDS_DIR)
            except: pass

        # 2. Flask w tle
        flask_thread = threading.Thread(target=run_flask_thread, daemon=True)
        flask_thread.start()

        # 2a. Globalny skrót klawiszowy dla Barrier -> Analyzer
        if (is_windows and user32) or (not is_windows and keyboard):
            threading.Thread(target=hotkey_listener, daemon=True).start()
        else:
            logging.warning("Hotkey listener not started (missing user32/keyboard module)")

        # 3. System Tray (musi być w głównym wątku)
        try:
            image = create_tray_icon()
            if pystray and item and image:
                menu = (
                    item(f'Metrix Agent: {hostname}', lambda: None, enabled=False),
                    item('Exit', on_quit)
                )
                icon = pystray.Icon("metrix_agent", image, f"Metrix: {hostname}", menu)
                icon.run()
            else:
                # Pystray lub grafika niedostępne - podtrzymujemy serwer w tle
                while True:
                    time.sleep(1)
        except Exception:
            # Fallback jeśli pystray nie działa (np. brak GUI na Linux headless)
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Metrix server interrupted, shutting down.")
