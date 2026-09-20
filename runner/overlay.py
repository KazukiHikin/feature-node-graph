import ctypes
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path

#--------------------------------------------------------------
#--自動操作中であることを画面全体に表示する
#--  ・画面を薄く暗くし、中央に案内文を出す
#--  ・フォーカスを奪わず、クリックは素通りする（赤枠と同じ）
#--  ・スクリーンショットには写らないので、画像認識に影響しない
#--
#--別プロセスとして動かす。script.pyから start() / stop() で制御する。
#--単体で見た目を確認したい時: python -m runner.overlay --show-in-capture
#--------------------------------------------------------------

ENABLED = True
DIM_ALPHA = 0.35                    #暗くする度合い（0=透明、1=真っ黒）
MAIN_TEXT = "自動操作中"
SUB_TEXT = "何かキーを押すと中断します"
FONT_MAIN = ("Yu Gothic UI", 40, "bold")
FONT_SUB = ("Yu Gothic UI", 16)
TEXT_COLOR = "white"
TRANSPARENT_KEY = "#010203"         #文字の層で、この色の部分を透明にする

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020      #クリックを素通りさせる
WS_EX_NOACTIVATE = 0x08000000       #フォーカスを奪わない
WS_EX_TOOLWINDOW = 0x00000080       #タスクバーに出さない
WDA_EXCLUDEFROMCAPTURE = 0x00000011 #スクリーンショットに写さない

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010

PROJECT_ROOT = Path(__file__).resolve().parent.parent
user32 = ctypes.windll.user32


# ===== script.py から使う側 =====

def start():
    #案内表示を別プロセスで起動する。戻り値は stop() に渡す
    if not ENABLED:
        return None
    return subprocess.Popen(
        [sys.executable, "-m", "runner.overlay", str(os.getpid())],
        cwd=PROJECT_ROOT,
    )


def stop(process):
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()


# ===== 別プロセスとして動く側 =====

def _apply_window_styles(window, exclude_from_capture):
    hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(
        hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
    )
    if exclude_from_capture:
        user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def _hwnd(window):
    return user32.GetParent(window.winfo_id()) or window.winfo_id()


def _place_dim_below_text(dim_layer, text_layer):
    #「暗い層を文字の層の直下に置く」と相対的に指定する。
    #HWND_TOPMOST指定では最前面グループ内の順番までは変えられないため
    user32.SetWindowPos(_hwnd(dim_layer), _hwnd(text_layer), 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def _restore_foreground(previous_hwnd):
    #tkinterは表示の瞬間にフォーカスを奪う。奪った直後なら返すことが許されているので、元の窓に戻す
    if previous_hwnd and user32.GetForegroundWindow() != previous_hwnd:
        user32.SetForegroundWindow(previous_hwnd)


def _parent_is_alive(parent_pid):
    #親(script.py)が落ちたら自分も終了する。表示が残り続けるのを防ぐ
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, parent_pid)
    if not handle:
        return False
    code = ctypes.c_ulong()
    ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(handle)
    return code.value == STILL_ACTIVE


def _run(parent_pid, exclude_from_capture):
    previous_foreground = user32.GetForegroundWindow()

    root = tk.Tk()
    width, height = root.winfo_screenwidth(), root.winfo_screenheight()

    #層1: 画面全体を薄く暗くする
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", DIM_ALPHA)
    root.configure(bg="black")
    root.geometry(f"{width}x{height}+0+0")

    #層2: 文字だけを不透明で重ねる（暗くする層に文字を書くと文字まで薄くなるため分ける）
    text_layer = tk.Toplevel(root)
    text_layer.overrideredirect(True)
    text_layer.attributes("-topmost", True)
    text_layer.attributes("-transparentcolor", TRANSPARENT_KEY)
    text_layer.configure(bg=TRANSPARENT_KEY)
    text_layer.geometry(f"{width}x{height}+0+0")
    tk.Label(text_layer, text=MAIN_TEXT, fg=TEXT_COLOR, bg=TRANSPARENT_KEY,
             font=FONT_MAIN).place(relx=0.5, rely=0.44, anchor="center")
    tk.Label(text_layer, text=SUB_TEXT, fg=TEXT_COLOR, bg=TRANSPARENT_KEY,
             font=FONT_SUB).place(relx=0.5, rely=0.54, anchor="center")

    root.update()
    _apply_window_styles(root, exclude_from_capture)
    _apply_window_styles(text_layer, exclude_from_capture)
    _restore_foreground(previous_foreground)
    root.update()

    def keep_text_on_top():
        #tkinterは描画更新のたびに暗い層を最前面に持ち上げ直し、文字に被せてしまう。
        #一度直しても戻されるので、定期的に並び順を直す
        _place_dim_below_text(root, text_layer)
        root.after(500, keep_text_on_top)

    def watch_parent():
        #親(script.py)が落ちたら自分も終了する
        if parent_pid and not _parent_is_alive(parent_pid):
            root.destroy()
            return
        root.after(1000, watch_parent)

    keep_text_on_top()
    watch_parent()
    root.mainloop()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    parent = int(args[0]) if args else None
    _run(parent, exclude_from_capture="--show-in-capture" not in sys.argv)
