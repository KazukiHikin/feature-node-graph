import ctypes
import time
from ctypes import wintypes

import pyautogui
import pygetwindow as gw

#--------------------------------------------
#--------NIKKEのウィンドウを前面(アクティブ)にする
#--------------------------------------------
#前面になっていないと、最初のクリックが「窓を選ぶ」動作に使われてボタンに届かない。
#
#「NIKKE」をタイトルに含む窓はゲーム以外にも複数ある：
#  ・VSCodeやエクスプローラー（フォルダ名 python-NIKKE-autoplay を表示しているため）
#  ・ブラウザ（GitHubのリポジトリページなど）
#  ・ゲーム自身が持つ画面外の小さな隠れ窓
#タイトルの部分一致で1つ目を取ると、これらを誤って前面にしてしまい、クリックが吸われる。
#そのため「タイトルが完全一致」かつ「nikke.exeの窓」かつ「画面内にある」ものだけを対象にする。

WINDOW_TITLE = "NIKKE"
PROCESS_NAME = "nikke.exe"
RETRY_MAX = 3
SW_RESTORE = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
GW_HWNDNEXT = 2
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
IGNORED_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW"}   #タスクバー・デスクトップ

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def _owner_process_name(hwnd):
    #窓を持っているプログラムのファイル名。管理者権限のプロセスでも取得できる方法を使う
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return None
    buf = ctypes.create_unicode_buffer(1024)
    size = ctypes.c_ulong(1024)
    ok = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
    kernel32.CloseHandle(handle)
    return buf.value.rsplit("\\", 1)[-1].lower() if ok else None


def _find_main_window():
    candidates = []
    for w in gw.getWindowsWithTitle(WINDOW_TITLE):
        if w.title != WINDOW_TITLE:                     #部分一致（VSCode等）を除外
            continue
        if not w.visible or w.left < -10000 or w.top < -10000:  #画面外の隠れ窓を除外
            continue
        owner = _owner_process_name(w._hWnd)
        if owner is not None and owner != PROCESS_NAME:  #別プログラムの窓を除外
            continue
        candidates.append(w)
    if not candidates:
        return None
    return max(candidates, key=lambda w: w.width * w.height)


def _raise_to_top(hwnd):
    #アクティブになっても、見た目の重なり順は他の窓の後ろに残ることがある。
    #「一瞬だけ最前面に固定して、すぐ解除する」と重なり順が確実に一番上になる（Windowsの定番の手）
    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
    user32.BringWindowToTop(hwnd)


def _rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r


def _is_cloaked(hwnd):
    #ストアアプリ等は「表示中」扱いのまま画面に出ていないことがある（DWMのcloak）。それは被りに数えない
    cloaked = ctypes.c_int(0)
    DWMWA_CLOAKED = 14
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return cloaked.value != 0


def _class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _overlapping_windows_above(hwnd):
    #hwndより重なり順が上で、hwndに被っている普通の窓を返す。
    #除外: 案内・赤枠（クリックを素通りさせる透明な窓）、ツールウィンドウ、タスクバー、非表示扱いの窓
    target = _rect(hwnd)
    result = []
    h = user32.GetTopWindow(None)
    while h and h != hwnd:
        if user32.IsWindowVisible(h) and not _is_cloaked(h):
            ex = user32.GetWindowLongW(h, GWL_EXSTYLE)
            if not (ex & WS_EX_TRANSPARENT) and not (ex & WS_EX_TOOLWINDOW) \
                    and _class_name(h) not in IGNORED_CLASSES:
                r = _rect(h)
                if r.left < target.right and r.right > target.left and r.top < target.bottom and r.bottom > target.top:
                    result.append(h)
        h = user32.GetWindow(h, GW_HWNDNEXT)
    return result


def _push_below(other, hwnd):
    #otherをhwndのすぐ下に移す（最小化も移動もしない）
    user32.SetWindowPos(other, hwnd, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def _bring_to_front(hwnd):
    #Windowsは他の窓が前面にいる時、勝手に前面を奪うのを制限している。
    #前面の窓の入力スレッドに一時的に相乗りすると、その制限を越えて前面にできる
    foreground = user32.GetForegroundWindow()
    if foreground != hwnd:
        foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
        my_thread = kernel32.GetCurrentThreadId()
        attached = bool(foreground_thread) and foreground_thread != my_thread \
            and user32.AttachThreadInput(my_thread, foreground_thread, True)
        try:
            user32.ShowWindow(hwnd, SW_RESTORE)     #最小化されていたら戻す
            user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(my_thread, foreground_thread, False)

    _raise_to_top(hwnd)
    time.sleep(0.3)

    #それでも被っている窓（ブラウザ等）があれば、その窓をゲームのすぐ下に移す
    blockers = _overlapping_windows_above(hwnd)
    for other in blockers:
        _push_below(other, hwnd)
    if blockers:
        time.sleep(0.3)

    return user32.GetForegroundWindow() == hwnd and not _overlapping_windows_above(hwnd)


def activate_window():
    #各ステップの前に毎回呼ばれる。既に前面で被る窓も無ければ、ほぼ即座に戻る
    #マウスが画面の隅に移動すると強制的に停止する機能OFF
    pyautogui.FAILSAFE = False

    window = _find_main_window()
    if window is None:
        print(f"{WINDOW_TITLE}のウィンドウが見つかりません")
        print("")
        return False

    hwnd = window._hWnd
    already_front = user32.GetForegroundWindow() == hwnd and not _overlapping_windows_above(hwnd)
    if already_front:
        return True

    print(f"{WINDOW_TITLE}を前面にします")
    for attempt in range(1, RETRY_MAX + 1):
        if _bring_to_front(hwnd):
            print(f"{WINDOW_TITLE}のウィンドウが前面になりました（{window.width}x{window.height}）")
            print("")
            time.sleep(1)   #前面化後1秒待機
            return True
        print(f"{WINDOW_TITLE}を前面にできませんでした。{attempt}/{RETRY_MAX}回目、再試行します")
        time.sleep(0.5)

    print(f"警告: {WINDOW_TITLE}を前面にできませんでした。クリックが効かない可能性があります")
    print("")
    return False
