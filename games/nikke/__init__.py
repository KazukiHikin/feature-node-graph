from pathlib import Path

#NIKKE固有の置き場。runnerはここを知らず、script.py / server.py が渡す
_HERE = Path(__file__).resolve().parent
IMAGE_DIR = _HERE / "img"          #クリックする画像（画像認識に使う）
SCREEN_DIR = _HERE / "screens"     #各ステップの画面全体（editorでの表示用。認識には使わない）
FLOW_DIR = _HERE / "flows"
