import sys
from pathlib import Path

import cv2
import numpy as np
import pyautogui
from PIL import Image, ImageDraw

from runner.image_io import read_image

#--------------------------------------------------------------
#--画像がどこに、どれくらいの一致率で見つかるかを確認する道具
#--画像を差し替える時の確認用。自動化処理からは使わない
#--
#--使い方(リポジトリのルートフォルダから実行):
#--  python -m runner.debug_match                 → 画像フォルダ内の全画像をまとめて確認
#--  python -m runner.debug_match interception    → 指定した画像だけ確認
#--------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIR = PROJECT_ROOT / "games" / "nikke" / "img"   #確認したい画像の置き場
OUTPUT_DIR = PROJECT_ROOT / "debug_out"
MARGIN = 120        #切り出す時に枠の周囲に残す余白


def check(image_name, screen_pil=None, save=True):
    #image_name: 「arc」でも「arc.png」でも、フルパスでも可
    image_path = Path(image_name)
    if image_path.suffix == "":
        image_path = image_path.with_suffix(".png")
    full_path = image_path if image_path.is_absolute() else IMAGE_DIR / image_path

    needle = read_image(full_path)
    if needle is None:
        print(f"[NG] 画像を読み込めません: {full_path}")
        return None

    if screen_pil is None:
        screen_pil = pyautogui.screenshot()
    screen = cv2.cvtColor(np.array(screen_pil), cv2.COLOR_RGB2BGR)

    result = cv2.matchTemplate(screen, needle, cv2.TM_CCOEFF_NORMED)
    _, confidence, _, (left, top) = cv2.minMaxLoc(result)
    height, width = needle.shape[:2]
    center = (left + width // 2, top + height // 2)

    print(f"{image_path.name:28s} 一致率 {confidence:.3f}  位置 {(left, top)}  中央 {center}  サイズ {width}x{height}")

    if save:
        marked = screen_pil.convert("RGB")
        draw = ImageDraw.Draw(marked)
        draw.rectangle([left, top, left + width, top + height], outline=(255, 0, 0), width=4)
        draw.line([center[0] - 20, center[1], center[0] + 20, center[1]], fill=(255, 0, 0), width=2)
        draw.line([center[0], center[1] - 20, center[0], center[1] + 20], fill=(255, 0, 0), width=2)

        crop_box = (
            max(left - MARGIN, 0),
            max(top - MARGIN, 0),
            min(left + width + MARGIN, marked.width),
            min(top + height + MARGIN, marked.height),
        )
        OUTPUT_DIR.mkdir(exist_ok=True)
        out_path = OUTPUT_DIR / f"{image_path.stem}_match.png"
        marked.crop(crop_box).save(out_path)
        print(f"{'':28s} → {out_path}")

    return confidence, center


def crop_from_screen(left, top, width, height, save_as):
    #今の画面から切り出して、参照画像として保存する(画像の差し替え用)
    out_path = IMAGE_DIR / save_as
    pyautogui.screenshot().crop((left, top, left + width, top + height)).save(out_path)
    print(f"保存しました: {out_path} ({width}x{height})")
    return out_path


if __name__ == "__main__":
    targets = sys.argv[1:]
    if not targets:
        targets = sorted(p.name for p in IMAGE_DIR.glob("*.png"))

    #全画像を同じ1枚のスクショで比較する
    screen = pyautogui.screenshot()
    print(f"画面サイズ {screen.width}x{screen.height} で照合します")
    print("-" * 90)
    for name in targets:
        check(name, screen_pil=screen)
