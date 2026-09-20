import ctypes
import time
import tkinter as tk
from contextlib import contextmanager

#--------------------------------------------------------------
#--画像が見つかった位置を、クリックが終わるまで赤枠で画面に表示する
#--確認用の機能なので、表示に失敗しても自動化処理は止めない
#--
#--使い方:
#--  with highlight.box(left, top, width, height):
#--      pyautogui.click(...)      ← この間だけ枠が出る。抜けると自動で消える
#--------------------------------------------------------------

ENABLED = True          #Falseにすると枠を出さなくなる
HOLD_AFTER = 0.3        #クリック後、枠を消すまでの秒数（押した瞬間が見えるように少し残す）
TRANSPARENT_COLOR = "magenta"   #この色の部分が透明になる(枠以外を見えなくするため)

#枠は「白い縁取り + 赤い線」の二重線。赤いボタンの上でも白が浮くので、どんな背景でも見える
OUTLINE_COLOR = "white"
OUTLINE_WIDTH = 8       #白い縁取り全体の太さ（この内側に赤線を重ねる）
BORDER_COLOR = "red"
BORDER_WIDTH = 4        #赤い線の太さ。両側に (OUTLINE_WIDTH - BORDER_WIDTH) / 2 ずつ白が残る
PADDING = 6             #画像の輪郭より少し外側に枠を出し、ボタン自体を隠さないようにする
EXCLUDE_FROM_CAPTURE = True     #Falseにするとスクショに写る（見た目の確認用）

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020  #クリックが枠を素通りしてゲームに届くようにする
WS_EX_NOACTIVATE = 0x08000000   #枠がフォーカスを奪ってゲームが非アクティブになるのを防ぐ
WS_EX_TOOLWINDOW = 0x00000080   #タスクバーに出さない
WDA_EXCLUDEFROMCAPTURE = 0x00000011  #スクリーンショットに写さない（画像認識に影響させない）

user32 = ctypes.windll.user32


def _make_overlay_non_interactive(window):
    hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(
        hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
    )
    if EXCLUDE_FROM_CAPTURE:
        user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)


def _restore_foreground(previous_hwnd):
    #tkinterは表示の瞬間にフォーカスを奪う。奪った直後なら返せるので、元の窓(NIKKE)に戻す
    if previous_hwnd and user32.GetForegroundWindow() != previous_hwnd:
        user32.SetForegroundWindow(previous_hwnd)


def _create(left, top, width, height):
    previous_foreground = user32.GetForegroundWindow()

    #枠の太さと余白ぶん、窓を画像より大きく取る
    margin = PADDING + OUTLINE_WIDTH
    win_w, win_h = width + margin * 2, height + margin * 2

    root = tk.Tk()
    root.overrideredirect(True)      #タイトルバーや枠を消す
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", TRANSPARENT_COLOR)
    root.geometry(f"{win_w}x{win_h}+{left - margin}+{top - margin}")

    canvas = tk.Canvas(root, width=win_w, height=win_h,
                       bg=TRANSPARENT_COLOR, highlightthickness=0)
    canvas.pack()
    #線は指定した座標を中心に描かれるので、太い白線の上に細い赤線を同じ座標で重ねると二重線になる
    inset = OUTLINE_WIDTH // 2
    rect = (inset, inset, win_w - inset, win_h - inset)
    canvas.create_rectangle(*rect, outline=OUTLINE_COLOR, width=OUTLINE_WIDTH)
    canvas.create_rectangle(*rect, outline=BORDER_COLOR, width=BORDER_WIDTH)

    root.update()
    _make_overlay_non_interactive(root)
    _restore_foreground(previous_foreground)
    root.update()
    return root


@contextmanager
def box(left, top, width, height):
    root = None
    if ENABLED:
        try:
            root = _create(left, top, width, height)
        except Exception as e:
            print(f"(枠の表示に失敗しましたが処理は続行します: {e})")
    try:
        yield
        if root is not None:
            time.sleep(HOLD_AFTER)
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
