import sys
import threading

from runner import flow, overlay
from runner.listen_for_key import listen_for_key
from runner.singleton_flag import ProgramInterrupted
from games.nikke import IMAGE_DIR, FLOW_DIR
from games.nikke.window import activate_window


# -----管理者権限で実行すること------------------------------------
# -----NIKKEが管理者権限で動いているため、通常権限だとマウス操作が届かない----
#
# 使い方:
#   python script.py                              → 迎撃戦（既定の手順）
#   python script.py games/nikke/flows/xxx.json   → 指定した手順


DEFAULT_FLOW = FLOW_DIR / "interception.json"


if __name__ == "__main__":
    flow_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FLOW

    #----手順を読む。形がおかしければ、何も動かす前にここで止める
    try:
        steps = flow.load_flow(flow_path, IMAGE_DIR)
    except flow.FlowError as e:
        print(f"手順ファイルに問題があります: {e}")
        sys.exit(1)
    print(f"手順ファイル: {flow_path}")
    print(flow.describe(steps))
    print("")

    # listen_for_keyをバックグラウンドスレッドで実行
    thread = threading.Thread(target=listen_for_key, daemon=True)
    thread.start()  # スレッドを開始

    #----「自動操作中」の案内を表示（正常終了・中断・エラーのどれでも必ず消す）
    overlay_process = overlay.start()

    #----手順を順番に実行。各ステップの前にNIKKEを前面にする
    try:
        flow.run_flow(steps, IMAGE_DIR, before_each=activate_window)
        print("メインスクリプトの処理が終了しました")
    except ProgramInterrupted as e:
        print(f"キー入力により処理を中断しました:{e}")
    finally:
        overlay.stop(overlay_process)
