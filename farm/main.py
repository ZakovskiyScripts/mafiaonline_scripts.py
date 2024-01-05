import random
import time
import json
import telebot
import redis
from datetime import datetime
from dataclasses import dataclass, field
from secrets import token_hex
from mafiaonline.mafiaonline import Client
from mafiaonline.structures import Roles, RatingType
from typing import List

TG_TOKEN: str = ""
UPTIME: int = int(time.time())
config: str = input("config << ")
if not config:
    config = "default"
with open(f"./configs/{config}.json", "r", encoding="utf-8") as cfg:
    config = json.load(cfg)
HOST: str = config.get("host", "")
ROLE: int = config.get("role", [])
DEBUG: bool = config['debug']
TG_CHANNEL_ID: int = config["tg"]
REMOVE_FROM_SERVER_KILLED: bool = True
TITLE: str = config.get("room_title", "")
PASSWORD: str = config.get("room_password", "123")
MIN_LEVEL: int = config.get("min_level", 1)
VIP_ENABLED: bool = config.get("vip_enabled", False)
"""
    **MODE**
        - 1 -- победа отдается только мафиям
        - 2 -- победа отдается только мирным
        - 3 -- победа отдается в зависимости от выпавшей роли основного аккаунта
        - 4 -- основной аккаунт всегда будет проигрывать
"""
MODE: int = config['mode']
"""
    **FORCE**
        - true - победа зависит от основного аккаунта
        - false - победа не зависит от основного аккаунта
"""
FORCE: bool = config['force']
MAX_PLAYERS: int = config['max_players']
ACCOUNTS: List[str] = config['accounts'][str(MAX_PLAYERS)]
MAIN_ACCOUNT_DATA: List[str] = config["main"]
DISABLED_ROLES: List[int] = []
if MAX_PLAYERS == 11:
    DISABLED_ROLES = [Roles.SPY]
elif MAX_PLAYERS == 12:
    DISABLED_ROLES = [Roles.SPY, Roles.BODYGUARD]
MAFIAS: List[Roles] = [
    Roles.MAFIA,
    Roles.BARMAN,
    Roles.INFORMER,
    Roles.TERRORIST
]
CIVS: List[Roles] = [
    Roles.CIVILIAN,
    Roles.LOVER,
    Roles.SHERIFF,
    Roles.SPY,
    Roles.DOCTOR,
    Roles.JOURNALIST
]
ENABLED_ROLES: List[Roles] = [Roles.BODYGUARD, Roles.INFORMER, Roles.TERRORIST,
    Roles.SPY, Roles.DOCTOR, Roles.LOVER, Roles.JOURNALIST]
if MODE == 1:
    ENABLED_ROLES = [Roles.BARMAN, Roles.TERRORIST, Roles.LOVER, Roles.SPY]
tg_bot = telebot.TeleBot(TG_TOKEN)

@dataclass
class Player:
    client: Client
    role: "Roles" = -1
    email: str = ""
    password: str = ""
    abr: List = field(default_factory=lambda: [])
    alive: bool = False
    disconn: bool = False
    
    def get_nickname(self):
        return f"{self.client.user.username} ({self.client.id})"


class Farm:
    def __init__(self):
        self.accounts = []
        self.players = []
        self.self_role = 0
        self.room_id = ""
        self.mafia_main = None
        self.from_file()

    def from_file(self):
        for account in ACCOUNTS:
            data = account.split(":")
            self.accounts.append([data[0], data[1]])

    def search_role(self, player: Player) -> int:
        data = player.client._get_data("roles", True)
        tryings = 0
        while data["ty"] != "roles" and tryings != 3:
            data = player.client._get_data("roles", True)
            print("rerecvier")
            tryings += 1
            time.sleep(.5)

        return data["roles"][0]["r"] if data["ty"] == "roles" else -1

    def format_time(self) -> str:
        return f"{datetime.now().strftime('%H:%M:%S')}"

    @property
    def is_killing_mafia(self) -> bool:
        if MODE == 3:
            return self.self_role in CIVS
        if MODE == 4:
            return not (self.self_role in CIVS)
        return bool(MODE-1)

    @property
    def get_who_civs(self) -> List[Player]:
        return list(filter(lambda x: x.role in CIVS and x.alive, self.players))

    @property
    def get_who_mafia(self) -> List[Player]:
        return list(filter(lambda x: x.role in MAFIAS and x.alive, self.players))

    def get_who_civ_may_kill(self, role: int = 0) -> List[Player]:
        if role:
            if role in CIVS:
                return self.get_who_mafia
            elif role in MAFIAS:
                return self.get_who_civs
        if self.is_killing_mafia:
            return self.get_who_mafia
        return self.get_who_civs

    def get_who_mafia_may_kill(self) -> List[Player]:
        l = list(filter(lambda x: x.role not in MAFIAS and x.alive, self.players))
        if self.is_killing_mafia and len(list(filter(lambda x: x.role in [Roles.BARMAN, Roles.INFORMER] and x.alive, self.players))) >= 1:
            l = list(filter(lambda x: x.role in [Roles.BARMAN, Roles.INFORMER] and x.alive, self.players))
        disconnecting_list = list(filter(lambda x: x.disconn, l))
        return disconnecting_list if disconnecting_list else l

    def get_who_sheriff(self) -> List[Player]:
        return list(filter(lambda x: x.role == Roles.SHERIFF and x.alive, self.conn_players()))

    def get_who_doctor(self) -> List[Player]:
        return list(filter(lambda x: x.role == Roles.DOCTOR and x.alive, self.conn_players()))

    def get_who_lover(self) -> List[Player]:
        return list(filter(lambda x: x.role == Roles.LOVER and x.alive, self.conn_players()))

    def get_who_terrorist(self) -> List[Player]:
        return list(filter(lambda x: x.role == Roles.TERRORIST and x.alive, self.conn_players()))

    def get_who_journalist(self) -> List[Player]:
        return list(filter(lambda x: x.role == Roles.JOURNALIST and x.alive, self.conn_players()))

    def get_who_journalist_may_check(self) -> List[Player]:
        return list(filter(lambda x: x.role != Roles.JOURNALIST and Roles.JOURNALIST not in x.abr and x.alive, self.players))

    def get_who_sheriff_may_check(self) -> List[Player]:
        return list(filter(lambda x: x.role != Roles.SHERIFF and Roles.SHERIFF not in x.abr and x.alive, self.players))

    def get_who_lover_may_fucking(self) -> List[Player]:
        li = self.disconn_players if self.disconn_players else self.players
        return list(filter(lambda x: x.role not in [Roles.LOVER, Roles.TERRORIST] and x.alive, li))

    def get_who_terrorist_may_boom(self) -> List[Player]:
        if self.is_killing_mafia:
            return list(filter(lambda x: x.role != Roles.TERRORIST, self.get_who_mafia))
        return self.get_who_civs

    def get_who_doctor_may_health(self) -> List[Player]:
        who_health = [Roles.DOCTOR, Roles.INFORMER, Roles.BARMAN]
        if not self.is_killing_mafia:
            who_health = CIVS
        return list(filter(lambda x: x.role not in who_health and x.alive, self.players))

    def find_by_username(self, username: str) -> Player:
        return list(filter(lambda x: x.client.user.username == username and x.alive, self.players))

    def join_to_room(self, account: Client) -> None:
        account.join_room(self.room_id, PASSWORD)
        time.sleep(.2)
        account.create_player(self.room_id)

    def create_client(self, email: str, password: str) -> Player:
        while True:
            client = Client(debug=DEBUG)
            response = client.sign_in(email, password)
            if not response:
                client.__del__()
                time.sleep(0.5)
            else:
                return Player(client, -1, email, password, [], True, False)

    def rehost(self, skip_timer: bool = False) -> None:
        if not skip_timer:
            print("\nПересоздаем. ждём 26 секунд\n")
        for player in self.conn_players():
            player.client.logout()
            player.client.__del__()
            
        self.played = False
        self.rh = False
        if not skip_timer:
            time.sleep(13)
            print('go')

    def log(self, log: str, tg: bool = False, svodka_id: int = None) -> None:
        if not tg:
            log = f"{self.format_time()} | {log}"
            self.svodka_text += f"{log}\n"
        print(log)
        try:
            if tg:
                btns = None
                if svodka_id:
                    btns = telebot.types.InlineKeyboardMarkup().add(telebot.types.InlineKeyboardButton('Сводка', url=f't.me/mafiaonlinefarm_bot?start={svodka_id}'))
                tg_bot.send_message(TG_CHANNEL_ID, log, reply_markup=btns)
        except Exception as e:
            print(f'error send log: {e}')

    def shuher(self, uid: str = "user_57e6cce718056") -> bool:
        profile = self.mafia_main.get_user(uid)['uu']
        if profile['on'] == 1:
            return profile['slc']
        return ""
        
    def conn_players(self) -> List[Player]:
        return list(filter(lambda x: not x.disconn and x.alive, self.players))
        
    @property
    def disconn_players(self) -> List[Player]:
        return list(filter(lambda x: x.disconn and x.alive, self.players))
        
    def get_listener(self, current_listener: Client = None) -> None:
        listeners = self.get_who_mafia
        if self.is_killing_mafia:
            listeners = self.get_who_civs
        if current_listener:
            listeners = list(filter(lambda x: x.client.id != current_listener.id, listeners))
        return random.choice(list(filter(lambda x: not x.disconn, listeners))).client

    def get_host(self) -> Client:
        return self.mafia_main if not HOST else list(filter(lambda x: x.email == HOST, self.players))[0].client

    def start(self):
        s = 1
        self.log(f'скрипт перезапустился. режим: {MODE}. аккаунт - {MAIN_ACCOUNT_DATA[0]}', True)
        self.rh = True
        shuhers = 0
        stopers = 0
        for i in range(99999999):
            room_time = time.time()
            self.players: List[Player] = []
            for account in self.accounts:
                self.players.append(self.create_client(account[0], account[1]))
            self.mafia_main_data: Player = self.create_client(MAIN_ACCOUNT_DATA[0], MAIN_ACCOUNT_DATA[1])
            self.mafia_main = self.mafia_main_data.client
            self.players.append(self.mafia_main_data)
            while True:
                try:
                    
                    #rating = self.mafia_main.get_rating(RatingType.WINS)["rul"]
                    #self.mafia_main.select_language("en")
                    time.sleep(.2)
                    room = self.get_host().create_room(ENABLED_ROLES, TITLE, max_players=MAX_PLAYERS, password=PASSWORD, min_level=MIN_LEVEL, vip_enabled=VIP_ENABLED)
                    
                    break
                except Exception as e:
                    
                    time.sleep(.5)
            shuher = self.shuher()
            if shuher:
                if shuher != "en":
                    self.log("! Шухер, но не на англ сервере, поэтому скип.", True)
                else:
                    self.log(f"! ШУХЕР НА {shuher} СЕРВЕРЕ !\n ждём 10 минут", True)
                    time.sleep(600)
                    shuhers += 1
                    continue
            self.svodka_text = f"[👤] аккаунт: {self.mafia_main_data.get_nickname()}\n"
            self.log("Создалась комната")
            self.room_id = room.room_id
            for index, account in enumerate(self.players):
                self.join_to_room(account.client)
                time.sleep(0.3)
            self.log("Все вошли")
            self.played = True
            last_empty_packet_time = 0
            day_gs = 0
            
            listener_account = self.mafia_main
            #if self.rh:
            #    self.rehost()
            while self.played:
                data = listener_account.listen(True)
                data_type = data.get("ty")
                
                if data_type == "gs":
                    game_type = data["s"]
                    if game_type == 2:
                        
                        self.log("Игра началась")
                    elif game_type == 1:
                        
                        self.log("Ждём начала")
                    else:
                        self.log("\n.\n")
                elif data_type == "ps" and self.players[0].role == -1:
                    for index, account in enumerate(self.players):
                        role = self.search_role(account)
                        if role == -1:
                            self.rehost()
                            break
                        self.players[index].role = role
                        if account.client.id == self.mafia_main.id:
                            self.self_role = role
                            
                            self.log(f"Номер твоей роли ({self.mafia_main.id}): {self.self_role}")
                        else:
                            if role in DISABLED_ROLES:
                                account.client.__del__()
                                self.players[index].disconn = True
                                self.log("отключаем:")
                            self.log(f"у игрока {account.get_nickname()} роль: {role}")
                    if MODE == 4 or (not FORCE and MODE in [1, 2]):
                        self.log(f"Убиваем: {'МАФОВ' if self.is_killing_mafia else 'МИРОВ'}")
                        
                    elif (ROLE and self.self_role not in ROLE) or (not ROLE and FORCE and MODE != 3 and ((self.self_role in CIVS and not self.is_killing_mafia) or
                                                (self.self_role in MAFIAS and self.is_killing_mafia))):
                        self.rehost()
                        break
                    listener_account = self.get_listener()
                    
                elif data_type == "gd":
                    type_day = data["d"]
                    if type_day == 1:
                        pass
                    elif type_day == 2:
                        self.log("Чатятся")
                    elif type_day == 3:
                        pass
                elif data_type == "gf":
                    work_time = time.time() - UPTIME
                    of_hours = ((s/work_time)*60)*60
                    of_sytki = int(of_hours*24)
                    work_time_hours = int(work_time / 3600)
                    work_time_minutes = (work_time%3600)//60
                    self.log(f"[🏆] {s} игра закончилась\n[⏳] {int(time.time()-room_time)} секунд\n[👤] роль: {self.self_role}\n[🔎] +{data['a']} авторитета, +{data['ex']} опыта\n\n[⏰] ~{of_sytki} за сутки\n[⏰] ~{of_hours} за час\n\n[💼] скрипт работает {work_time_hours} часов {work_time_minutes} минут\n\n[👀] всего шухеров: {shuhers} ({shuhers * 10} потерянных минут)\n[] всего сбоев: {stopers}", not (s % 1))
                    #all_wins = self.mafia_main.user.wins_as_mafia + self.mafia_main.user.wins_as_peaceful + 1
                    #versus_rating = [b for b in rating if b["rv"] >= all_wins][-1]
                    #versus_rating_index = rating.index(versus_rating) + 1
                    #versus_rating_difference = versus_rating["rv"] - all_wins
                    #self.log(f"сейчас ты на {versus_rating_index+1} месте,\nнужно ещё {versus_rating_difference} побед чтобы перейти на {versus_rating_index}")
                    self.rehost(True)
                    self.rh = True
                    s += 1
                elif data_type == "ud":
                    data = data["data"]
                    if len(data) > 3:
                        a = True
                        for d in data:
                            if d.get("r") == None:
                                a = False
                        if not a:
                            continue
                        self.log("закончилась сбойная игра", True)
                        self.rehost(True)
                        self.rh = True
                        s += 1
                elif data_type == "m" or data_type == "ms":
                    
                    if data_type == "ms":
                        message = data["m"][-1]
                    else:
                        message = data["m"]
                    if message["t"] == 5:
                        self.log("Мафия в чате")
                        try:
                            fucking_list = self.get_who_lover_may_fucking()
                            fucker = self.get_who_lover()
                            if fucking_list and fucker:
                                fucked = random.choice(fucking_list)
                                fucker[0].client.role_action(fucked.client.id, self.room_id)
                                self.log(f"Трахнули {fucked.get_nickname()}")
                        except Exception as e:
                            self.log(f"\n!!! Ошибка при траханье?????? {e} \n")
                    elif message["t"] in [3, 12]:
                        username = message['tx']
                        self.log(f"Убили {username}")
                        removed_player = self.find_by_username(username)
                        if not removed_player:
                            continue
                        for ind, player in enumerate(self.players):
                            if player.email == removed_player[0].email:
                                self.players[ind].alive = False
                        if REMOVE_FROM_SERVER_KILLED:
                            if not removed_player[0].disconn:
                                removed_player[0].client.__del__()
                            self.players.remove(removed_player[0])
                    elif message["t"] == 18:
                        username_boom = message['tx']
                        boom = message['uu']["u"]
                        self.log(f'{boom} взорвал {username_boom}')
                        for username in [username_boom, boom]:
                            removed_player = self.find_by_username(username)
                            if removed_player:
                                for ind, player in enumerate(self.players):
                                    if player.email == removed_player[0].email:
                                        self.players[ind].alive = False
                                if REMOVE_FROM_SERVER_KILLED:
                                    if not removed_player[0].disconn:
                                        removed_player[0].client.__del__()
                                    self.players.remove(removed_player[0])
                    elif message["t"] in [9, 13]:
                        died_user = self.find_by_username(message['tx'])[0]
                        killer_user = self.find_by_username(message.get('uu', {}).get('u'))[0]
                        self.log(f"{killer_user.get_nickname()} ударил в {died_user.get_nickname()}")
                    elif message["t"] == 6:
                        self.log("Мафия выбирает жертву")
                        try:
                            killing_list = self.get_who_mafia_may_kill()
                            killed = random.choice(killing_list)
                            for mafia in list(filter(lambda x: not x.disconn,self.get_who_mafia)):
                                if mafia.client.id == killed.client.id:
                                    mafia.client.role_action(random.choice(self.get_who_civs).client.id, self.room_id)
                                else:
                                    mafia.client.role_action(killed.client.id, self.room_id)
                        except Exception as e:
                            self.log(f"Ошибка при убийстве?????? {e}")
                        try:
                            killing_list = self.get_who_journalist_may_check()[:2]
                            journalist = self.get_who_journalist()
                            if journalist and killing_list:
                                for checkering in killing_list:
                                    for ind, player in enumerate(self.players):
                                        if player.email == checkering.email:
                                            self.players[ind].abr.append(Roles.JOURNALIST)
                                            
                                    journalist[0].client.role_action(checkering.client.id, self.room_id)
                        except Exception as e:
                            self.log(f"!!! Ошибка при журе?????? {e}")
                        time.sleep(.2)
                        try:
                            checked_list = self.get_who_sheriff_may_check()
                            sheriff = self.get_who_sheriff()
                            if checked_list and sheriff:
                                checked = random.choice(checked_list)
                                for ind, player in enumerate(self.players):
                                    if player.email == checked.email:
                                        self.players[ind].abr.append(Roles.SHERIFF)
                                
                                sheriff[0].client.role_action(checked.client.id, self.room_id)
                                self.log(f"Чекнул {checked.get_nickname()}")
                        except Exception as e:
                            self.log(f"!!! Ошибка при чеке?????? {e}")
                        try:
                            checked_list = self.get_who_doctor_may_health()
                            doctors = self.get_who_doctor()
                            for doctor in doctors:
                                checked = random.choice(checked_list)
                                doctor.client.role_action(checked.client.id, self.room_id)
                                self.log(f"Вылечил {checked.get_nickname()}")
                        except Exception as e:
                            self.log(f"!!! Ошибка при лечение?????? {e}")
                    elif message["t"] == 8:
                        day_gs += 1
                        if (MODE == 2 and day_gs > 3) or (MODE == 1 and day_gs > 6):
                            self.log("слишком много дневных гс, делаем рх", True)
                            self.rehost()
                            stopers += 1
                            break
                        self.log("Дневное гс")
                        
                        terr = self.get_who_terrorist()
                        boomeds = self.get_who_terrorist_may_boom()
                        ignore = []
                        print(terr)
                        print(boomeds)
                        if terr and boomeds:
                            boomed = random.choice(boomeds)
                            ignore = [terr[0].client.id, boomed.client.id]
                            try:
                                terr[0].client.role_action(boomed.client.id, self.room_id)
                            except:
                                terr[0].disconn = True
                                self.log("терр откинулся", True)
                            time.sleep(.4)
                            
                            
                        who_may_killed = list(filter(lambda x: x.client.id not in ignore, self.get_who_civ_may_kill()))
                        if who_may_killed:
                            who_killed = random.choice(who_may_killed)
                            for player in self.conn_players():
                                try:
                                    if player.client.id == who_killed.client.id:
                                        player.client.role_action(random.choice(self.get_who_civ_may_kill(player.role)).client.id, self.room_id)
                                    else:
                                        player.client.role_action(who_killed.client.id, self.room_id)
                                except:
                                    pass
                        
                elif data_type == "empty":
                    if not last_empty_packet_time:
                        last_empty_packet_time = time.time()
                    else:
                        if (time.time() - last_empty_packet_time) > 5:
                            self.log("ХАРД СБОЙ... скипаем")
                            #listener_account = self.get_listener(listener_account)
                            #for index, player in enumerate(self.players):
                            #    if player[0].user.username == listener_account.user.username:
                            #        try:
                            #            player[0].__del__()
                            #        except:
                            #            self.log("failed of end session", True)
                            #        resession = self.create_client(player[2][0], player[2][1])
                            #        self.join_to_room(resession[0])
                            #        self.players[index][0] = resession[0]
                            #        listener_account = resession[0]
                            last_empty_packet_time = 0
                            stopers+=1
                            self.rehost()
                elif not data_type:
                    last_empty_packet_time = 0
                    if data.get("t") and not int(data["t"]) % 10:
                        for index, player in enumerate(self.conn_players()):
                            try:
                                player.client.send_message_room("", self.room_id)
                            except Exception as e:
                                self.log(f"отвалился аккаунт {player.get_nickname()}. удаляем его из списка игроков: {e}", True)
                                self.players[index].disconn = True
                                size_disabled_accounts = len(self.disconn_players)
                                self.log(size_disabled_accounts)
                                if size_disabled_accounts > 5:
                                    self.log("отсоединилось больше 5 акков, делаем рехост", True)
                                    stopers+=1
                                    self.rehost()
                        #self.log(f">> [⌚] {data.get('t')}")
if __name__ == "__main__":
    farm = Farm()
    farm.start()
