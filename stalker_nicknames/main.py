import time
import telebot
from mafiaonline.mafiaonline import Client

"""
    Script powered by t.me/zakovskiy
"""
TG_CHANNEL_ID: int = -100
TG_BOT_TOKEN: str = ''

entertainers = [["email", "pass"]] # data from accounts that should be occupied by nicknames. 
trackeds = [["user_5c3dcdfc168516ca2b1ywv", ""],
    ["f8bda046-a635-4bc1-97d9-36d3d497d8d7", ""],
    ["5c50e2a7-7e68-4bee-838e-340dd8c05162", ""]] # ids of users that should be occupied.

main = Client()
main.sign_in(entertainers[-1][0], entertainers[-1][1])
main.__del__()
tg_bot = telebot.TeleBot(TG_BOT_TOKEN)

def log(log: str) -> None:
    print(log)
    try:
        if TG_BOT_TOKEN:
            tg_bot.send_message(TG_CHANNEL_ID, log)
    except Exception as e:
        print(f'error send tg log :: {e}')

def check_accounts() -> None:
    for i, tracked in enumerate(trackeds):
        try:
            account = main.user_get(tracked[0])
        except Exception as e:
            print(f"frd :: {e}")
            time.sleep(50)
            continue
        nickname = account["u"]
        if tracked[1] == "":
            trackeds[i][1] = nickname
            print('~set nickname')
        elif nickname != tracked[1]:
            enter_nickname(nickname)
            del trackeds[i]
        time.sleep(1)

def enter_nickname(nickname: str) -> None:
    main = Client()
    main.sign_in(entertainers[0][0], entertainers[0][1])
    main.uns(nickname)
    del entertainers[0]
    log(f"заняли ник {nickname}")

while True:
    check_accounts()
    time.sleep(20)
