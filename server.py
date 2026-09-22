import json
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import keyboard

from runner import flow, overlay
from runner.singleton_flag import SingletonFlag, ProgramInterrupted
from games.nikke import IMAGE_DIR
from games.nikke.window import activate_window

#--------------------------------------------------------------
#--ブラウザ(editor)とPythonの橋渡し
#--  自分のPC内だけで動く小さなWebサーバー。外部には公開されない。
#--
#--  GET  /              editorの画面を返す
#--  GET  /api/status    今の進行状況を返す（ブラウザが0.5秒ごとに聞きに来る）
#--  POST /api/start     送られてきたグラフを手順として実行開始
#--  POST /api/stop      中断
#--
#--管理者権限で実行すること（NIKKEへのクリックに必要）
#--  python server.py   → ブラウザが自動で開く
#--------------------------------------------------------------

HOST = "127.0.0.1"      #自分のPCからしか接続できない
PORT = 8765
EDITOR_HTML = Path(__file__).resolve().parent / "editor" / "feature-node-graph.html"


class RunState:
    #進行状況。実行スレッドが書き、HTTPスレッドが読むのでロックで守る
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.running = False
        self.finished = False
        self.error = None
        self.current = None
        self.order = []
        self.steps = {}     #node_id → {"name", "state", "confidence", "message"}

    def snapshot(self):
        with self.lock:
            return {
                "running": self.running,
                "finished": self.finished,
                "error": self.error,
                "current": self.current,
                "order": list(self.order),
                "steps": {k: dict(v) for k, v in self.steps.items()},
            }


state = RunState()
flag = SingletonFlag()
run_thread = None


def _on_event(event):
    with state.lock:
        node_id = event.get("node_id")
        if event["type"] == "step_start":
            state.current = node_id
            state.steps[node_id]["state"] = "running"
        elif event["type"] == "step_done":
            state.steps[node_id]["state"] = "done"
            state.steps[node_id]["confidence"] = round(event["confidence"], 3)
        elif event["type"] == "step_failed":
            state.steps[node_id]["state"] = "failed"
            state.steps[node_id]["message"] = event["message"]
        elif event["type"] == "step_interrupted":
            state.steps[node_id]["state"] = "interrupted"


def _run(steps):
    #先にゲームを前面に出す。案内表示は「表示前に前面だった窓」にフォーカスを戻すので、
    #この順番にしないとブラウザが前面に戻ってしまう
    activate_window()
    overlay_process = overlay.start()
    try:
        flow.run_flow(steps, IMAGE_DIR, before_each=activate_window, on_event=_on_event)
        print("手順がすべて完了しました")
    except ProgramInterrupted as e:
        print(f"中断しました: {e}")
        with state.lock:
            state.error = f"中断しました: {e}"
    except Exception as e:
        print(f"エラーで停止しました: {e}")
        traceback.print_exc()
        with state.lock:
            state.error = str(e)
    finally:
        overlay.stop(overlay_process)
        with state.lock:
            state.running = False
            state.finished = True
            state.current = None


def start_run(graph):
    global run_thread
    with state.lock:
        if state.running:
            return False, "実行中です。停止してから開始してください"
    try:
        steps = flow.parse_flow(graph, IMAGE_DIR)
    except flow.FlowError as e:
        return False, str(e)

    flag.reset()
    with state.lock:
        state.reset()
        state.running = True
        state.order = [s.node_id for s in steps]
        state.steps = {s.node_id: {"name": s.name, "state": "pending", "confidence": None, "message": ""}
                       for s in steps}
    print(flow.describe(steps))
    run_thread = threading.Thread(target=_run, args=(steps,), daemon=True)
    run_thread.start()
    return True, f"{len(steps)}ステップを開始しました"


def stop_run():
    with state.lock:
        if not state.running:
            return False, "実行中ではありません"
    flag.request_stop()
    return True, "中断を要求しました"


def watch_keyboard():
    #実行中に何かキーが押されたら中断する（緊急停止用。ブラウザの「停止」と同じ効果）
    while True:
        event = keyboard.read_event(suppress=False)
        if event.event_type == keyboard.KEY_DOWN:
            with state.lock:
                running = state.running
            if running:
                print(f"「{event.name}」キーが押されました。処理を中断します。")
                flag.request_stop()


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            return None

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            body = EDITOR_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/status":
            self._send_json(state.snapshot())
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/api/start":
            graph = self._read_json()
            if graph is None:
                self._send_json({"ok": False, "message": "JSONとして読めませんでした"}, 400)
                return
            ok, message = start_run(graph)
            self._send_json({"ok": ok, "message": message}, 200 if ok else 400)
        elif self.path == "/api/stop":
            ok, message = stop_run()
            self._send_json({"ok": ok, "message": message})
        else:
            self._send_json({"error": "not found"}, 404)

    def log_message(self, format, *args):
        #0.5秒ごとの問い合わせで画面が埋まらないよう、通常のアクセスログは出さない
        pass


class Server(ThreadingHTTPServer):
    #Windowsでは既定だと同じポートに2つ目のサーバーが立ってしまい、問い合わせがどちらに届くか不定になる。
    #使用中なら起動時にエラーで止める
    allow_reuse_address = False


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)     #ログをファイルに向けても即座に出るように
    try:
        server = Server((HOST, PORT), Handler)
    except OSError:
        print(f"ポート{PORT}は使用中です。既に server.py が起動していませんか？（そちらのウィンドウで Ctrl+C）")
        sys.exit(1)
    threading.Thread(target=watch_keyboard, daemon=True).start()
    url = f"http://{HOST}:{PORT}/"
    print(f"起動しました: {url}")
    print("ブラウザの画面から「開始」で実行できます。終了は Ctrl+C")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("終了します")
        flag.request_stop()
