import threading

# ------------
# ------中断フラグをプログラム全体で共有するためのクラス
# ------モジュール変数やインスタンスを都度作る方式ではファイル間で共有できなかったため、
# ------__new__でインスタンスを1つだけ作るシングルトンにしている
# ------_変数名のアンダーバーはクラス内のみで完結されるべき変数という意味の慣習
# ------------


class ProgramInterrupted(Exception):
    #中断フラグが立った際に処理を中断させるための例外
    pass


class SingletonFlag:

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:       #インスタンスが無い場合にON
            with cls._lock:         #ロックを使用して同時アクセスを制限する
                if not cls._instance:   #ロック解除後にインスタンス生成の2重チェック
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.stop_requested = False
        self.lock = threading.Lock()

    def is_stop_requested(self):
        with self.lock:
            return self.stop_requested

    def request_stop(self):
        with self.lock:
            self.stop_requested = True
            print("シングルトンフラグが中断を検知しました")

    def reset(self):
        with self.lock:
            self.stop_requested = False
