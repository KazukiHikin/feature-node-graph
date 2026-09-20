import json
from dataclasses import dataclass
from pathlib import Path

from runner.wait_for_image import wait_for_image

#--------------------------------------------------------------
#--ノードグラフ(editor)で書き出したJSONを読み、手順として順番に実行する
#--
#--ノードと手順の対応:
#--  ノード名          → ステップ名（ログに出る）
#--  項目「画像」      → クリックする画像のファイル名（画像フォルダ内）
#--  項目「一致率」    → 画像認識の閾値（省略時 0.7）
#--  項目「リトライ」  → 画像が見つかるまで待つ回数（省略時 10）
#--順番は線をたどって決める。線が入ってこないノードが開始点。
#--1本道のみ対応。分岐・合流・つながっていないノードはエラーにする。
#--------------------------------------------------------------

FIELD_IMAGE = "画像"
FIELD_CONFIDENCE = "一致率"
FIELD_RETRIES = "リトライ"
DEFAULT_CONFIDENCE = 0.7
DEFAULT_RETRIES = 10


class FlowError(Exception):
    #手順JSONの形がおかしい時の例外。メッセージにノード名を入れて、どこを直せばいいか分かるようにする
    pass


@dataclass
class Step:
    node_id: str
    name: str
    image: str
    confidence: float
    retries: int


def load_flow(json_path, image_dir):
    #JSONを読み、順番に並んだStepのリストを返す。画像ファイルの存在もここで確認する
    path = Path(json_path)
    if not path.exists():
        raise FlowError(f"手順ファイルが見つかりません: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise FlowError(f"手順ファイルのJSONが壊れています: {path} ({e})")

    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise FlowError("手順ファイルにノードがありません")

    ordered = _order_nodes(nodes, data.get("connections") or [])
    steps = [_to_step(node) for node in ordered]

    missing = [s for s in steps if not (Path(image_dir) / s.image).exists()]
    if missing:
        names = "、".join(f"「{s.name}」の {s.image}" for s in missing)
        raise FlowError(f"画像ファイルが見つかりません: {names}（置き場: {image_dir}）")
    return steps


def _node_name(node):
    return node.get("name") or node.get("id") or "(名前なし)"


def _order_nodes(nodes, connections):
    by_id = {n["id"]: n for n in nodes if isinstance(n, dict) and n.get("id")}
    next_of = {}        #ノードid → 線の先のノードid
    has_incoming = set()

    for c in connections:
        if not isinstance(c, dict):
            continue
        src, dst = c.get("from"), c.get("to")
        if src not in by_id or dst not in by_id:
            continue    #存在しないノードへの線は無視（editor側も同じ扱い）
        if src in next_of:
            raise FlowError(f"ノード「{_node_name(by_id[src])}」から線が2本以上出ています。分岐にはまだ対応していません")
        next_of[src] = dst
        has_incoming.add(dst)

    starts = [n for n in by_id.values() if n["id"] not in has_incoming]
    if len(starts) != 1:
        names = "、".join(f"「{_node_name(n)}」" for n in starts) or "なし"
        raise FlowError(f"開始ノード（線が入ってこないノード）は1つにしてください。今は{len(starts)}個: {names}")

    ordered = []
    seen = set()
    current = starts[0]["id"]
    while current is not None:
        if current in seen:
            raise FlowError(f"線が輪になっています（ノード「{_node_name(by_id[current])}」に戻ってきました）")
        seen.add(current)
        ordered.append(by_id[current])
        current = next_of.get(current)

    if len(ordered) != len(by_id):
        left = [f"「{_node_name(n)}」" for n in by_id.values() if n["id"] not in seen]
        raise FlowError(f"線でつながっていないノードがあります: {'、'.join(left)}")
    return ordered


def _to_step(node):
    name = _node_name(node)
    fields = {}
    for f in node.get("fields") or []:
        if isinstance(f, dict):
            fields[str(f.get("label", "")).strip()] = str(f.get("value", "")).strip()

    image = fields.get(FIELD_IMAGE)
    if not image:
        raise FlowError(f"ノード「{name}」に項目「{FIELD_IMAGE}」がありません（クリックする画像のファイル名を入れてください）")

    try:
        confidence = float(fields.get(FIELD_CONFIDENCE) or DEFAULT_CONFIDENCE)
    except ValueError:
        raise FlowError(f"ノード「{name}」の「{FIELD_CONFIDENCE}」が数値ではありません: {fields.get(FIELD_CONFIDENCE)!r}")
    if not 0.0 < confidence <= 1.0:
        raise FlowError(f"ノード「{name}」の「{FIELD_CONFIDENCE}」は0より大きく1以下にしてください: {confidence}")

    try:
        retries = int(fields.get(FIELD_RETRIES) or DEFAULT_RETRIES)
    except ValueError:
        raise FlowError(f"ノード「{name}」の「{FIELD_RETRIES}」が整数ではありません: {fields.get(FIELD_RETRIES)!r}")
    if retries < 1:
        raise FlowError(f"ノード「{name}」の「{FIELD_RETRIES}」は1以上にしてください: {retries}")

    return Step(node_id=node["id"], name=name, image=image, confidence=confidence, retries=retries)


def describe(steps):
    lines = [f"手順（{len(steps)}ステップ）:"]
    for i, s in enumerate(steps, 1):
        lines.append(f"  {i}. {s.name}  画像={s.image}  一致率={s.confidence}  リトライ={s.retries}")
    return "\n".join(lines)


def run_flow(steps, image_dir, before_each=None):
    #before_each: 各ステップの直前に呼ぶ関数（ゲームの窓を前面にする等）
    for i, step in enumerate(steps, 1):
        print(f"===== ステップ {i}/{len(steps)}: {step.name} =====")
        if before_each is not None:
            before_each()
        wait_for_image(
            image_path=str(Path(image_dir) / step.image),
            image_name=step.name,
            pass_confidence=step.confidence,
            retry_maxcount=step.retries,
        )
