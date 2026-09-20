import threading
from runner import overlay
from runner.listen_for_key import listen_for_key
from runner.singleton_flag import ProgramInterrupted
from games.nikke.interception import order_interception


# -----管理者権限で実行すること------------------------------------
# -----NIKKEが管理者権限で動いているため、通常権限だとマウス操作が届かない----


if __name__ == "__main__":
    # listen_for_keyをバックグラウンドスレッドで実行
    thread = threading.Thread(target=listen_for_key, daemon=True)
    thread.start()  # スレッドを開始

    #----「自動操作中」の案内を表示（正常終了・中断・エラーのどれでも必ず消す）
    overlay_process = overlay.start()

    #----画像クリック処理の開始
    try:
        order_interception()
        print("メインスクリプトの処理が終了しました")
    except ProgramInterrupted as e:
        print(f"キー入力により処理を中断しました:{e}")
    finally:
        overlay.stop(overlay_process)
