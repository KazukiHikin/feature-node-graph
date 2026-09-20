from pathlib import Path

from games.nikke.window import activate_window
from runner.wait_for_image import wait_for_image

#--------------
#--迎撃戦を自動化
#--（段階1で、この固定の手順をノードグラフから書き出したJSONに置き換える予定）
#--------------

IMG = Path(__file__).resolve().parent / "img"


def order_interception():
    #----ウィンドウを検索してアクティブにする----
    activate_window()
    #----「アーク」の画像をクリック----
    wait_for_image(image_path=str(IMG / "arc.png"), image_name="アーク", pass_confidence=0.7)
    #----「迎撃戦の画像」をクリック----
    wait_for_image(image_path=str(IMG / "interception.png"), image_name="迎撃戦", pass_confidence=0.7)
    #----「迎撃戦-特殊個体」の画像をクリック----
    wait_for_image(image_path=str(IMG / "interception_special.png"), image_name="迎撃戦-特殊個体", pass_confidence=0.7)
    #----「戦闘突入の画像」をクリック----
    wait_for_image(image_path=str(IMG / "Entering_battle.png"), image_name="戦闘突入", pass_confidence=0.7)
    #----「空いてるところをタップ」の画像をクリック----
    wait_for_image(image_path=str(IMG / "tap_empty_space.png"), image_name="空いてるところをタップ", pass_confidence=0.7, retry_maxcount=180)
