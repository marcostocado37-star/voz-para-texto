from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import json
import os
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parent
MAX_TEXT_CHARS = 100_000
MAX_BODY_BYTES = 1_000_000
RATE_LIMIT = 20
RATE_WINDOW_SECONDS = 60
VOICES = [
    {"name": "pt-br", "culture": "Português do Brasil"},
    {"name": "pt-pt", "culture": "Português de Portugal"},
]
VOICE_IDS = {voice["name"] for voice in VOICES}
requests_by_ip = defaultdict(deque)
rate_lock = threading.Lock()
tts_slots = threading.BoundedSemaphore(2)


class Handler(BaseHTTPRequestHandler):
    server_version = "TextoEmOndas/1.0"

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def send_bytes(self, status, content_type, body, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_text(self, status, message):
        self.send_bytes(status, "text/plain; charset=utf-8", message.encode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            try:
                body = (ROOT / "index.html").read_bytes()
            except OSError:
                return self.send_text(500, "Não foi possível abrir o site.")
            return self.send_bytes(200, "text/html; charset=utf-8", body)
        if path == "/voices":
            body = json.dumps(VOICES, ensure_ascii=False).encode("utf-8")
            return self.send_bytes(200, "application/json; charset=utf-8", body)
        if path == "/health":
            return self.send_text(200, "ok")
        return self.send_text(404, "Página não encontrada.")

    def _allowed_request(self):
        now = time.monotonic()
        ip = self.client_address[0]
        with rate_lock:
            history = requests_by_ip[ip]
            while history and now - history[0] > RATE_WINDOW_SECONDS:
                history.popleft()
            if len(history) >= RATE_LIMIT:
                return False
            history.append(now)
        return True

    def do_POST(self):
        if urlparse(self.path).path != "/speak":
            return self.send_text(404, "Página não encontrada.")
        try:
            body_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_text(400, "Tamanho do texto inválido.")
        if body_length < 1 or body_length > MAX_BODY_BYTES:
            return self.send_text(413, "O texto enviado ultrapassa o limite permitido.")
        try:
            text = self.rfile.read(body_length).decode("utf-8").strip()
        except UnicodeDecodeError:
            return self.send_text(400, "O texto precisa estar em UTF-8.")
        if not text:
            return self.send_text(400, "Digite ou carregue um texto primeiro.")
        if len(text) > MAX_TEXT_CHARS:
            return self.send_text(413, "O texto deve ter até 100 mil caracteres.")
        if not self._allowed_request():
            return self.send_text(429, "Muitas conversões em pouco tempo. Aguarde um minuto e tente novamente.")
        if not tts_slots.acquire(blocking=False):
            return self.send_text(503, "O conversor está ocupado. Tente novamente em instantes.")

        try:
            query = parse_qs(urlparse(self.path).query)
            requested_voice = query.get("voice", ["pt-br"])[0]
            voice = requested_voice if requested_voice in VOICE_IDS else "pt-br"
            try:
                rate = float(query.get("rate", ["1.0"])[0])
            except (TypeError, ValueError):
                rate = 1.0
            rate = max(0.7, min(1.3, rate))
            words_per_minute = round(175 * rate)

            with tempfile.TemporaryDirectory(prefix="texto-em-ondas-") as temp_dir:
                text_file = Path(temp_dir) / "texto.txt"
                wav_file = Path(temp_dir) / "fala.wav"
                text_file.write_text(text, encoding="utf-8")
                try:
                    result = subprocess.run(
                        ["espeak-ng", "-v", voice, "-s", str(words_per_minute),
                         "-f", str(text_file), "-w", str(wav_file)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        timeout=240,
                        check=False,
                    )
                except subprocess.TimeoutExpired:
                    return self.send_text(504, "A conversão demorou demais. Tente um texto menor.")
                except FileNotFoundError:
                    return self.send_text(503, "O mecanismo de voz não está instalado no servidor.")
                if result.returncode != 0 or not wav_file.exists():
                    return self.send_text(500, "Não foi possível gerar o áudio WAV.")
                audio = wav_file.read_bytes()
            return self.send_bytes(
                200,
                "audio/wav",
                audio,
                {"Content-Disposition": 'attachment; filename="texto-em-ondas.wav"'},
            )
        finally:
            tts_slots.release()


def main():
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    print(f"Texto em Ondas disponível na porta {port}.")
    server.serve_forever()


if __name__ == "__main__":
    main()
