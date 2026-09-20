import ctypes
import time

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


def _bring_to_front(hwnd):
    #Windowsは他の窓が前面にいる時、勝手に前面を奪うのを制限している。
    #前面の窓の入力スレッドに一時的に相乗りすると、その制限を越えて前面にできる
    foreground = user32.GetForegroundWindow()
    if foreground == hwnd:
        return True

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

    time.sleep(0.3)
    return user32.GetForegroundWindow() == hwnd


def activate_window():
    print(f"{WINDOW_TITLE}のアクティブONの関数実行")
    #マウスが画面の隅に移動すると強制的に停止する機能OFF
    pyautogui.FAILSAFE = False

    window = _find_main_window()
    if window is None:
        print(f"{WINDOW_TITLE}のウィンドウが見つかりません")
        print("")
        return False

    for attempt in range(1, RETRY_MAX + 1):
        if _bring_to_front(window._hWnd):
            print(f"{WINDOW_TITLE}のウィンドウがアクティブになりました（{window.width}x{window.height}）")
            print("")
            time.sleep(1)   #アクティブ後1秒待機
            return True
        print(f"{WINDOW_TITLE}を前面にできませんでした。{attempt}/{RETRY_MAX}回目、再試行します")
        time.sleep(0.5)

    print(f"警告: {WINDOW_TITLE}を前面にできませんでした。クリックが効かない可能性があります")
    print("")
    return False
