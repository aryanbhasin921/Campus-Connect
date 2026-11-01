"""
CampusConnect one-click launcher (Windows / macOS / Linux).

Run by the double-click files:  Run CampusConnect.bat  |  Run CampusConnect.command  |  run.sh
What it does:
  1. creates a local virtual environment (.venv) the first time
  2. installs the required packages (Flask, Werkzeug) the first time
  3. picks a free port (5050 by default)
  4. starts the server and opens the browser
Press Ctrl+C (or close the window) to stop the server.
Use --no-venv to run with the Python that is already installed (skips steps 1-2).
"""
import os
import socket
import subprocess
import sys
import threading
import time
import venv
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT, ".venv")
DEFAULT_PORT = 5050


def venv_python():
    sub = "Scripts" if os.name == "nt" else "bin"
    exe = "python.exe" if os.name == "nt" else "python"
    return os.path.join(VENV_DIR, sub, exe)


def can_import(python, modules):
    code = "import " + ", ".join(modules)
    return subprocess.run([python, "-c", code], capture_output=True).returncode == 0


def ensure_environment(use_venv):
    if not use_venv:
        return sys.executable
    py = venv_python()
    if not os.path.exists(py):
        print("[1/3] Creating virtual environment (first run only)...")
        venv.EnvBuilder(with_pip=True, clear=False).create(VENV_DIR)
    if not can_import(py, ["flask", "werkzeug"]):
        print("[2/3] Installing required packages (first run only, needs internet)...")
        cmd = [py, "-m", "pip", "install", "--disable-pip-version-check", "Flask>=3.0.0", "Werkzeug>=3.0.0"]
        if os.environ.get("DB_TYPE", "sqlite").lower() == "mysql":
            cmd.append("mysql-connector-python>=8.3.0")
        if subprocess.call(cmd) != 0:
            sys.exit("\nCould not install packages. Check your internet connection and run again.")
    return py


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        return s.connect_ex(("127.0.0.1", port)) != 0


def pick_port():
    wanted = int(os.environ.get("PORT", DEFAULT_PORT))
    for port in range(wanted, wanted + 20):
        if port_is_free(port):
            return port
    sys.exit("No free port found near %d." % wanted)


def open_browser_when_ready(port):
    def worker():
        for _ in range(60):
            if not port_is_free(port):
                break
            time.sleep(0.5)
        else:
            return
        if not os.environ.get("NO_BROWSER"):
            webbrowser.open("http://localhost:%d" % port)
    threading.Thread(target=worker, daemon=True).start()


def main():
    if sys.version_info < (3, 8):
        sys.exit("Python 3.8 or newer is required (found %s)." % sys.version.split()[0])
    use_venv = "--no-venv" not in sys.argv
    py = ensure_environment(use_venv)
    port = pick_port()
    env = dict(os.environ, PORT=str(port))

    print("[3/3] Starting CampusConnect...")
    print("=" * 56)
    print("  Open:   http://localhost:%d" % port)
    print("  Admin:  admin@campusconnect.edu / admin123")
    print("  Demo:   passenger@campusconnect.edu / password123")
    print("  Stop:   press Ctrl+C or close this window")
    print("=" * 56)
    open_browser_when_ready(port)
    try:
        subprocess.call([py, "app.py"], cwd=ROOT, env=env)
    except KeyboardInterrupt:
        print("\nCampusConnect stopped.")


if __name__ == "__main__":
    main()
