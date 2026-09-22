from pathlib import Path

import cv2
import numpy as np

#--------------------------------------------------------------
#--画像ファイルの読み込み
#--
#--cv2.imread はWindowsで日本語を含むパスの画像を読めない（Noneが返る）。
#--ノード名から作るファイル名は日本語になりうるので、
#--ファイルを「バイトの塊」として読んでから画像に変換する方法を使う。
#--------------------------------------------------------------


def read_image(path):
    #読めた場合はOpenCVの画像（BGR）、読めない場合は None を返す
    try:
        data = np.fromfile(str(path), dtype=np.uint8)    #日本語パスでも読める
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def read_image_or_raise(path):
    image = read_image(path)
    if image is None:
        raise FileNotFoundError(f"画像を読み込めません。パスかファイル形式を確認してください: {Path(path).name}")
    return image
