import time
import random
import json
from dataclasses import dataclass
from mafiaonline.structures.models import Roles
from mafiaonline import mafiaonline
from typing import List

@dataclass
class Player:
    id: str
    client: mafiaonline.Client
    role: "Roles" = 0
    email: str = ""
    password: str = ""

@dataclass
class OtherPlayer:
    id: str
    username: str

config = input("config << ")
if not config:
    config = "default"
with open(f"./configs/{config}.json", "r") as cfg:
    config = json.load(cfg)
DEBUG: bool = config['debug']
TG_CHANNEL_ID: int = config["tg"]
ROOM_SIZE: int = config["players"]
ACCOUNTS: list = config["accounts"]

random.shuffle(ACCOUNTS)


accounts: List[Player] = []

def create_client(email: str, password: str) -> Player:
    while True:
        try:
            client = mafiaonline.Client()
            response = client.sign_in(email, password)
            client.select_language("ru")
        except:
            print('oooooups')
            time.sleep(1)
            continue
        if not response:
            client.delete()
            time.sleep(0.5)
        else:
            return Player(client.id, client, 0, email, password)

main_account = create_client(ACCOUNTS[0].split(":")[0], ACCOUNTS[0].split(":")[1])

#victim_id = "user_6011509c17743a2e1a5rwk"
victim_id = str(input("victim ID << "))

del ACCOUNTS[0]

room_id = ""

while True:
    user = main_account.client.get_user(victim_id)


    if user.get("rr", False):
        room = user["rr"]
        room_status = room["s"]
        if room_status == 2:
            print('[X] Игра уже идет, ждем 10 секунд')
            time.sleep(10)
        elif room_status == 0:
            room_id = room["o"]
            ACCOUNTS = ACCOUNTS[:ROOM_SIZE - 1 - room["pn"]]
            break
    else:
        print('[X] Комната не найдена, ждем 10 секунд')
        time.sleep(10)


def join_room(account):
    account.client.join_room(room_id)
    time.sleep(.2)
    account.client.create_player(room_id)

def recreate_client(**data):
    for account in accounts:
        try:
            account.client.delete()
            print("disconn")
        except Exception as e:
            print("hmm failed disconn acc")
    new_client = create_client(**data)
    join_room(new_client)
    return new_client

for account_data in ACCOUNTS:
    accounts.append(recreate_client(email=account_data.split(":")[0], password=account_data.split(":")[1]))

main_account.client.delete()
main_account = recreate_client(email=main_account.email, password=main_account.password)
accounts.append(main_account)

#for index, account in enumerate(accounts):
#   print(index)
#   recreate_client(email=account.email, password=account.password)

def search_role(account: Player) -> int:
    data = account.client._get_data("ud")
    data = data["data"]
    for d in data:
        if d["uo"] == account.id:
            return d["r"]

def get_who_lover():
    return list(filter(lambda x: x.role == Roles.LOVER, accounts))

def get_who_mafia_may_kill() -> List[OtherPlayer]:
    return other_accounts

def get_who_mafia() -> list:
    return list(filter(lambda x: x.role in Roles.MAFIAS, accounts))

def find_by_username(username: str) -> List[OtherPlayer]:
    return list(filter(lambda x: x.username == username, other_accounts))

other_accounts: List[OtherPlayer] = []
type = 0
last_empty_packet_time = 0
be_vote_night = False
while True:
    data = main_account.client.listen(True)
    data_type = data.get("ty")
    if data_type != "empty":
        print(data)
    if data_type == "roles" and type == 0:
        self_role = data["roles"][0]["r"]
        for index, account in enumerate(accounts):
            account = recreate_client(email=account.email, password=account.password)
            role = search_role(account)
            accounts[index].role = role
            accounts[index].client = account.client
            print(f"У игрока {account.client.user.username} ({account.id}) роль: {role}")
        print(f"Номер твоей роли ({main_account.id}): {self_role}")
        lover = get_who_lover()
        if not lover:
            raise Exception("У нас нет шлю =(")
        type = 1
        main_account = recreate_client(email=lover[0].email, password=lover[0].password)
    elif data_type == "pls":
        other_accounts.clear()
        players = data["pls"]
        for player in players:
            player_id = player["o"]
            for acc in accounts:
                if player_id == acc.id and player["a"] and player and player_id != victim_id:
                    other_accounts.append(OtherPlayer(player_id, player["uu"]["u"]))
    elif data_type in ["m", "ms"]:
        if data_type == "ms":
            message = data["m"][-1]
        else:
            message = data["m"]
        username = message.get('tx')
        if message["t"] in [3, 12, 18]:
            player = find_by_username(username)
            if player:
                other_accounts.remove(player)
                print(f'ливнул/убил {username}')
            else:
                print("Player not undefined o_O")
        elif message["t"] == 5:
            be_vote_night = False
            try:
                main_account = recreate_client(email=main_account.email, password=main_account.password)
                main_account.client.role_action(victim_id, room_id)
                print("шлюшнули?")
            except Exception as e:
                print(f"\n!!! Ошибка при шлюшенстве?????? {e} \n")
        elif message["t"] == 6 and not be_vote_night:
            be_vote_night = True
            print(">> [🌃🗡️]Мафия выбирает жертву")
            try:
                killing_list = get_who_mafia_may_kill()
                killed = killing_list[0]
                mafias = get_who_mafia()
                if not mafias:
                    print("[X] Некого убивать")
                for mafia in mafias:
                    mafia = recreate_client(email=mafia.email, password=mafia.password)
                    mafia.client.role_action(killed, room_id)
                    time.sleep(.3)
            except Exception as e:
                print(f"\n!!! Ошибка при убийстве?????? {e} \n")
        elif message["t"] == 8:
            print("\nУтреннее гс\n")
            try:
                who_may_killed = other_accounts
                if other_accounts:
                    who_killed = other_accounts[0].id
                    for player in accounts:
                        player = recreate_client(email=player.email, password=player.password)
                        player.client.role_action(who_killed, room_id)
                        time.sleep(.5)
                main_account = recreate_client(email=main_account.email, password=main_account.password)
            except Exception as e:
                print(f"\n!!! Ошибка при гс?????? {e} \n")
        else:
            print(username)
    elif not data_type:
        last_empty_packet_time = 0
        print(f">> [⌚] {data.get('t')}")