from pathlib import Path

#NIKKE固有の置き場。runnerはここを知らず、script.pyが渡す
IMAGE_DIR = Path(__file__).resolve().parent / "img"
FLOW_DIR = Path(__file__).resolve().parent / "flows"
