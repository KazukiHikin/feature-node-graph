import keyboard
from runner.singleton_flag import SingletonFlag

#--------------------------------------------------------------
#--キー入力を監視し、何かキーが押されたら中断フラグを立てる
#--script.pyからバックグラウンドスレッドで実行される
#--------------------------------------------------------------


def listen_for_key():
    flag_manager = SingletonFlag()
    print("キー入力を監視中-----（何かキーを押すと処理を中断します）")
    while not flag_manager.is_stop_requested():
        #read_eventはキー入力があるまで待機するので、ポーリングが不要
        event = keyboard.read_event(suppress=False)
        if event.event_type == keyboard.KEY_DOWN:
            print(f"「{event.name}」キーが押されました。処理を中断します。")
            flag_manager.request_stop()
            break
