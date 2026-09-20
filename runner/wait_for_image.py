import cv2
import numpy as np
import pyautogui
import time
from pathlib import Path
from runner import highlight
from runner.singleton_flag import SingletonFlag, ProgramInterrupted

#カレントディレクトリに関係なく画像を見つけられるよう、プロジェクトフォルダを基準にする
PROJECT_ROOT = Path(__file__).resolve().parent.parent

#クリックの動き。NIKKEはタッチ操作を模しているため、到着直後の一瞬の押下は取りこぼされることがある
MOVE_DURATION = 1.0     #マウスを目的地まで動かす秒数
CLICK_SETTLE = 0.15     #到着してから押すまでの間
CLICK_HOLD = 0.08       #押している時間

#クリック後の確認。画面が変わっていなければ押し直す
CLICK_VERIFY_WAIT = 1.5 #クリック後、画面が変わるのを待つ秒数
CLICK_RETRY_MAX = 3     #押し直す上限


def _click(center):
    pyautogui.moveTo(center[0], center[1], duration=MOVE_DURATION)
    time.sleep(CLICK_SETTLE)
    pyautogui.mouseDown()
    time.sleep(CLICK_HOLD)
    pyautogui.mouseUp()


def _locate_image(full_image_path, pass_confidence):
    #画面から画像を探し、((左, 上, 幅, 高さ), 一致率)を返す。閾値未満なら矩形はNone。
    #pyautogui.locateOnScreenは一致率を返さないため、cv2で直接判定している。
    needle = cv2.imread(full_image_path)
    if needle is None:
        raise FileNotFoundError(f"画像を読み込めません。パスかファイル形式を確認してください: {full_image_path}")

    screen = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
    result = cv2.matchTemplate(screen, needle, cv2.TM_CCOEFF_NORMED)
    _, confidence, _, top_left = cv2.minMaxLoc(result)

    if confidence < pass_confidence:
        return None, confidence

    height, width = needle.shape[:2]
    return (top_left[0], top_left[1], width, height), confidence


#指定された画像が見つかるまで待機し、見つかったらクリック。
#最大試行回数に達したら例外をスローする。
#image_path (str): 検索する画像ファイルのパス(フルパス推奨。相対パスならリポジトリのルート基準)
#pass_confidence (float): 画像検索の信頼度 (0.0~1.0)。
#retry_maxcount (int): 最大試行回数。

#関数に初期値を設定することで呼び出し時に引数を設定しない場合にデフォルトで関数で設定した値が使われる
def wait_for_image (image_path,image_name, pass_confidence, retry_maxcount=10) :
    time_count = 1.0
    retry_count = 0
    flag_manager = SingletonFlag()
    full_image_path = str(PROJECT_ROOT / image_path)

    while retry_count < retry_maxcount:
        #中断フラグが立っていたら処理を中断する
        if flag_manager.is_stop_requested():
            raise ProgramInterrupted(f"「{image_name}」の待機中にキー入力を検知したため処理を中断しました")

        box, confidence = _locate_image(full_image_path, pass_confidence)

        if box is None:
            #time関数で1秒待ってから再度処理が流れる
            retry_count += 1
            print(f"画像、{image_name}が見つかりません。一致率{confidence:.3f}/必要{pass_confidence}。画像パス、{image_path}。{retry_count}/{retry_maxcount}回目の再確認。{time_count}秒後に再確認します")
            time.sleep(time_count)
            continue

        #見つかったのでクリック。押した後に画像が消えていなければ（＝画面が変わっていなければ）押し直す
        for attempt in range(1, CLICK_RETRY_MAX + 1):
            if flag_manager.is_stop_requested():
                raise ProgramInterrupted(f"「{image_name}」のクリック中にキー入力を検知したため処理を中断しました")

            left, top, width, height = box
            center = (left + width // 2, top + height // 2)

            #どこを押そうとしているかを、クリックが終わるまで赤枠で見せる
            with highlight.box(left, top, width, height):
                _click(center)

            time.sleep(CLICK_VERIFY_WAIT)
            box, still_confidence = _locate_image(full_image_path, pass_confidence)
            if box is None:
                print("")
                print(f"OK:{image_name}のセンター位置にマウス移動＋クリックが完了しました。一致率{confidence:.3f}/必要{pass_confidence}")
                print("")
                #関数処理終了させるためreturnを使う
                return center

            print(f"クリックしましたが画面が変わっていません（{image_name}がまだ見えている。一致率{still_confidence:.3f}）。{attempt}/{CLICK_RETRY_MAX}回目、押し直します")

        raise RuntimeError(f"「{image_name}」を{CLICK_RETRY_MAX}回クリックしても画面が変わりませんでした。処理を中断します")

    raise RuntimeError(f"画像{image_path}が見つかりませんでした。最大試行回数{retry_maxcount}回に到達しました。raise呼び出しの為処理を中断します")
