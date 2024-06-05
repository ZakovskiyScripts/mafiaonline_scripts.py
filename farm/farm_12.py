import random
import time
import json
import logging
from datetime import datetime
from dataclasses import dataclass, field
from secrets import token_hex
from mafiaonline.mafiaonline import Client
from mafiaonline.structures import Roles, RatingType
from typing import List

BUILD = "v1.0"
# Создаем логгер
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Создаем обработчик для записи в файл
current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_path = f"logs/{current_datetime}.log"  # путь к папке с логами и название файла
file_handler = logging.FileHandler(log_path)
file_handler.setLevel(logging.DEBUG)

# Создаем обработчик для вывода в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Создаем форматирование для логов
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
# Добавляем обработчик в логгер
logger.addHandler(file_handler)
logger.addHandler(console_handler)
COOLDOWN: int = 14
UPTIME: int = int(time.time())
config = input("config << ")
if not config:
    config = "default"
with open(f"./configs/{config}.json", "r", encoding="utf8") as cfg:
    config = json.load(cfg)
HOST: str = config.get("host", "")
ROLE: int = config.get("role", [])

DEBUG: bool = config['debug']
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
FORCE = config['force']
MAX_PLAYERS = config['max_players']
ACCOUNTS = config['accounts'][str(MAX_PLAYERS)]
MAIN_ACCOUNT_DATA: List[str] = config["main"]
MAFIAS = [
    Roles.MAFIA,
    Roles.BARMAN,
    Roles.INFORMER,
    Roles.TERRORIST
]
CIVS = [
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
    ENABLED_ROLES: List[Roles] = [Roles.BARMAN, Roles.TERRORIST, Roles.LOVER, Roles.SPY]

@dataclass
class Player:
    client: Client
    role: "Roles" = -1
    email: str = ""

    password: str = ""
    abr: List = field(default_factory=lambda: [])
    alive: bool = False
    disconn: bool = False
    proxy: str = ""
    tryings: int = 0
    
    def get_nickname(self):
        return f"{self.client.user.username} ({self.client.id})"
        
    def role_action(self, user_id: str, room_id: str, resess: bool = False):
        try:
            self.client.role_action(user_id, room_id)
            if resess:
                time.sleep(.5)
                self.client.__del__()
        except:
            tryings = 0
            while True:
                if tryings > 3:
                    return
                client = Client(debug=DEBUG, proxy=self.proxy)
                response = client.sign_in(self.email, self.password)
                if not response:
                    client.__del__()
                    time.sleep(0.5)
                    tryings += 1
                else:
                    self.client = client
                    break
            self.client.join_room(room_id, PASSWORD)
            time.sleep(.3)
            self.client.create_player(room_id)
            time.sleep(.3)
            self.role_action(user_id, room_id, True)

class Farm:
    def __init__(self):
        self.accounts = []
        self.players = []
        self.self_role = 0
        self.proxies = 0
        self.room_id = ""
        self.mafia_main = None
        self.from_file()

    def from_file(self):
        """
        Это файл с данными от аккаунтов в формате '''email:password'''
        """
        for account in ACCOUNTS:
            self.accounts.append(account.split(":"))

    def search_role(self, player: Player) -> int:
        data = player.client._get_data("roles", True)
        tryings = 0
        while data["ty"] != "roles" and tryings != 3:
            data = player.client._get_data("roles", True)
            print("rerecvier")
            tryings += 1
            time.sleep(.5)

        return data["roles"][0]["r"] if data["ty"] == "roles" else -1

    def format_time(self):
        return f"{datetime.now().strftime('%H:%M:%S')}"

    @property
    def is_killing_mafia(self) -> bool:
        if MODE == 3:
            #return self.self_role in [Roles.CIVILIAN, Roles.LOVER, Roles.SHERIFF, Roles.SPY] and self.find_by_username('kwepfi')[1] in [Roles.CIVILIAN, Roles.LOVER, Roles.SHERIFF, Roles.SPY]
            return self.self_role in CIVS
        if MODE == 4:
            return not (self.self_role in CIVS)
        return bool(MODE-1)

    @property
    def get_who_civs(self):
        return list(filter(lambda x: x.role in CIVS and x.alive, self.players))

    @property
    def get_who_mafia(self):
        return list(filter(lambda x: x.role in MAFIAS and x.alive, self.players))


    def get_who_civ_may_kill(self, role: int = 0):
        if role:
            if role in CIVS:
                return self.get_who_mafia
            elif role in MAFIAS:
                return self.get_who_civs
        if self.is_killing_mafia:
            return self.get_who_mafia
        return self.get_who_civs

    def get_who_mafia_may_kill(self):
        l = list(filter(lambda x: x.role not in MAFIAS and x.alive, self.players))
        if self.is_killing_mafia and len(list(filter(lambda x: x.role in [Roles.BARMAN, Roles.INFORMER] and x.alive, self.players))) >= 1:
            l = list(filter(lambda x: x.role in [Roles.BARMAN, Roles.INFORMER] and x.alive, self.players))
        disconnecting_list = list(filter(lambda x: x.disconn, l))
        return disconnecting_list if disconnecting_list else l

    def get_who_sheriff(self):
        return list(filter(lambda x: x.role == Roles.SHERIFF and x.alive, self.sorted_players()))

    def get_who_doctor(self):
        return list(filter(lambda x: x.role == Roles.DOCTOR and x.alive, self.sorted_players()))

    def get_who_lover(self):
        return list(filter(lambda x: x.role == Roles.LOVER and x.alive, self.sorted_players()))

    def get_who_terrorist(self):
        return list(filter(lambda x: x.role == Roles.TERRORIST and x.alive, self.sorted_players()))

    def get_who_journalist(self):
        return list(filter(lambda x: x.role == Roles.JOURNALIST and x.alive, self.sorted_players()))

    def get_who_journalist_may_check(self) -> List[Player]:
        return list(filter(lambda x: x.role != Roles.JOURNALIST and Roles.JOURNALIST not in x.abr and x.alive, self.players))

    def get_who_sheriff_may_check(self) -> List[Player]:
        return list(filter(lambda x: x.role != Roles.SHERIFF and Roles.SHERIFF not in x.abr and x.alive, self.players))

    def get_who_lover_may_fucking(self):
        li = self.disconn_players if self.disconn_players else self.players
        return list(filter(lambda x: x.role not in [Roles.LOVER, Roles.TERRORIST] and x.alive, li))

    def get_who_terrorist_may_boom(self):
        if self.is_killing_mafia:
            return list(filter(lambda x: x.role != Roles.TERRORIST, self.get_who_mafia))
        return self.get_who_civs

    def get_who_doctor_may_health(self):
        who_health = [Roles.DOCTOR, Roles.INFORMER, Roles.BARMAN]
        if not self.is_killing_mafia:
            who_health = CIVS
        return list(filter(lambda x: x.role not in who_health and x.alive, self.players))

    def find_by_username(self, username: str) -> Player:
        return list(filter(lambda x: x.client.user.username == username and x.alive, self.players))

    def join_to_room(self, account: Client):
        account.join_room(self.room_id, PASSWORD)
        time.sleep(.2)
        account.create_player(self.room_id)

    def create_client(self, account: list) -> Player:
        tryings = 0
        while True:
            proxy = [] 
            if len(account) > 2 and account[2]:
                self.proxies += 1
                proxy = account[2].split("/") if type(account[2]) is str else account[2]
                print(proxy)
            try:
                client = Client(debug=DEBUG, proxy=proxy)
            except:
                time.sleep(3)
                continue
            response = client.sign_in(account[0], account[1])
            if not response:
                client.__del__()
                time.sleep(0.5)
                tryings += 1
            else:
                client.dashboard()
                player = Player(client, -1, account[0], account[1], [], True, False, proxy)
                print(f"{player.get_nickname()} успешно залогинился")
                return player

    def rehost(self, skip_timer: bool = False, hard: bool = False) -> None:
        if not skip_timer:
            print(f"\nПересоздаем. ждём {COOLDOWN} секунд\n")
        for player in self.players:
            player.role = -1
            if player.disconn:
                self.log("hehe")
                player.client = self.create_client([player.email, player.password, player.proxy]).client
            player.disconn = False
            player.alive = True
            player.abr = []
            if hard:
                player.client.__del__()
            else:
                try:
                    player.client.remove_player(self.room_id)
                except:
                    player.client = self.create_client([player.email, player.password, player.proxy]).client
                    
            time.sleep(0.5)
            
        self.played = False
        self.rh = False
        if not skip_timer:
            time.sleep(COOLDOWN)
            print('go')
            
        if hard:
            self.players = []
            for account in self.accounts:
                self.players.append(self.create_client(account))
            self.mafia_main_data: Player = self.create_client(MAIN_ACCOUNT_DATA)
            self.players.append(self.mafia_main_data)

            
    def sorted_players(self):
        return sorted(list(filter(lambda p: Roles.LOVER not in p.abr and p.alive, self.players)), key=lambda x: x.disconn)


    def log(self, log: str, tg: bool = False) -> None:
        if not tg:
            log = f"{self.format_time()} | {log}"
        logger.debug(log)

    def shuher(self, uid: str = "user_57e6cce718056") -> bool:
        profile = self.get_host().get_user(uid)['uu']
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
        return random.choice(list(filter(lambda x: not x.disconn, listeners)))

    def get_host(self) -> Client:
        return self.mafia_main_data.client if not HOST else list(filter(lambda x: x.email == HOST, self.players))[0].client

    def start(self):
        s = 1
        self.log(f'скрипт перезапустился. режим: {MODE}. аккаунт - {MAIN_ACCOUNT_DATA[0]}', True)
        self.rh = True
        shuhers = 0
        stopers = 0
        rehosts = 0
        self.players: List[Player] = []
        for account in self.accounts:
            self.players.append(self.create_client(account))
        self.mafia_main_data: Player = self.create_client(MAIN_ACCOUNT_DATA)
        DISABLED_ROLES: List[int] = []
        if MAX_PLAYERS >= 11:
            if self.proxies == 0:
                DISABLED_ROLES = [Roles.SPY, Roles.BODYGUARD, Roles.CIVILIAN]
        self.players.append(self.mafia_main_data)
        for i in range(99999999):
            room_time = time.time()
            while True:
                try:
                    
                    #rating = self.mafia_main.get_rating(RatingType.WINS)["rul"]
                    #self.mafia_main.select_language("en")
                    time.sleep(.2)
                    room = self.get_host().create_room(ENABLED_ROLES, TITLE, max_players=MAX_PLAYERS, password=PASSWORD, min_level=MIN_LEVEL, vip_enabled=VIP_ENABLED)
                    
                    break
                except Exception as e:
                    
                    time.sleep(.5)
            self.svodka_text = ""
            self.log("Создалась комната")
            self.players = self.players[::-1]
            self.room_id = room.room_id
            for index, account in enumerate(self.players):
                while True:
                    try:
                        self.join_to_room(account.client)
                        time.sleep(.3)
                        break
                    except:
                        self.log('a')
                        account.client = self.create_client([account.email, account.password, account.proxy]).client
                        time.sleep(.5)
            self.log("Все вошли")
            self.played = True
            last_empty_packet_time = 0
            day_gs = 0
            listener_account = self.mafia_main_data.client
            #if self.rh:
            #    self.rehost()
            while self.played:
                data = listener_account.listen(True)
                data_type = data.get("ty")
                #if True and data_type != "empty" and data_type:
                #    print(data)
                if data_type == "gs":
                    game_type = data["s"]
                    if game_type == 2:
                        
                        self.log("Игра началась")
                    elif game_type == 1:
                        
                        self.log("Ждём начала")
                    else:
                        self.log("\n.\n")
                elif data_type == "ps" and self.players[0].role == -1:
                    a = False
                    for index, account in enumerate(self.players):
                        role = self.search_role(account)
                        if role == -1:
                            a = True
                            break
                        self.players[index].role = role
                        if role in DISABLED_ROLES:
                            account.client.__del__()
                            self.players[index].disconn = True
                            self.log("отключаем:")
                        if account.client.id == self.mafia_main_data.client.id:

                            self.self_role = role
                            
                            self.log(f"Номер твоей роли ({self.mafia_main_data.client.id}): {self.self_role}")
                        else:
                            self.log(f"у игрока {account.get_nickname()} роль: {role}")
                    if a:
                        print(account)
                        self.rehost(hard=True)
                        stopers += 1
                        break
                    if MODE == 4 or (not FORCE and MODE in [1, 2]):
                        self.log(f"Убиваем: {'МАФОВ' if self.is_killing_mafia else 'МИРОВ'}")
                        
                    elif (ROLE and self.self_role not in ROLE) or (not ROLE and FORCE and MODE != 3 and ((self.self_role in CIVS and not self.is_killing_mafia) or
                                                (self.self_role in MAFIAS and self.is_killing_mafia))) or (self.find_by_username("iuqdwjxozc") and self.find_by_username("iuqdwjxozc")[0].role == Roles.INFORMER):
                        rehosts += 1
                        self.rehost()
                        break
                    listener_account = self.get_listener()
                    self.log(f"Слушатель: {listener_account.get_nickname()}")
                    listener_account = listener_account.client
                elif data_type == "gd":
                    type_day = data["d"]
                    if type_day == 1:
                        pass
                    elif type_day == 2:
                        if day_gs >= 1:
                            print("mnogo dnevnih gs")
                            self.rehost()
                            stopers += 1
                            break
                        day_gs += 1
                        self.log("Чатятся")
                    elif type_day == 3:
                        pass
                elif data_type == "gf":
                    work_time = time.time() - UPTIME
                    of_hours = ((s/work_time)*60)*60
                    of_sytki = int(of_hours*24)
                    work_time_hours = int(work_time / 3600)
                    work_time_minutes = (work_time%3600)//60
                    ext = ""
                    if not (s % 150):
                        user_info = listener_account.get_user(self.mafia_main_data.client.id)['uu']
                        wins_as_mafia = user_info['wim']
                        wins_as_peacefull = user_info['wip']

                        ext = f"\n[] авторитета: {user_info['a']}\n[] игр: {user_info['pg']}\n[] до след. лвл: {user_info['nle'] - user_info['ex']} EXP. (~{(user_info['nle'] - user_info['ex'])/data['ex']} игр)\n[] м/м: {wins_as_peacefull/wins_as_mafia} ({wins_as_mafia}|{wins_as_peacefull})"
                    self.log(f"{self.mafia_main_data.get_nickname()}{ext}\n\n[🏆] {s} игра закончилась\n[⏳] {int(time.time()-room_time)} секунд\n[👤] роль: {self.self_role}\n[🔎] +{data['a']} авторитета, +{data['ex']} опыта\n\n[⏰] ~{of_sytki} за сутки\n[⏰] ~{of_hours} за час\n\n[💼] скрипт работает {work_time_hours} часов {work_time_minutes} минут\n\n[👀] всего шухеров: {shuhers} ({shuhers * 10} потерянных минут)\n[] всего сбоев: {stopers}\n[] всего рехостов: {rehosts} ({rehosts*(COOLDOWN+5)} секунд)", not (s % 1))
                    #all_wins = self.mafia_main.user.wins_as_mafia + self.mafia_main.user.wins_as_peaceful + 1
                    #versus_rating = [b fo-*                                 r b in rating if b["rv"] >= all_wins][-1]
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
                                fucker[0].role_action(fucked.client.id, self.room_id)
                                fucked.abr.append(Roles.LOVER)
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
                                self.players[ind].disconn = True
                        if REMOVE_FROM_SERVER_KILLED:
                            if not removed_player[0].disconn:
                                removed_player[0].client.__del__()

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
                                        self.players[ind].disconn = True
                                if REMOVE_FROM_SERVER_KILLED:
                                    if not removed_player[0].disconn:
                                        removed_player[0].client.__del__()
                    elif message["t"] in [9, 13]:
                        died_user = self.find_by_username(message['tx'])[0]
                        killer_user = self.find_by_username(message.get('uu', {}).get('u'))[0]
                        self.log(f"{killer_user.get_nickname()} ударил в {died_user.get_nickname()}")
                    elif message["t"] == 6:
                        time.sleep(.5)
                        self.log("Мафия выбирает жертву")
                        try:
                            killing_list = self.get_who_mafia_may_kill()
                            killed = random.choice(killing_list)
                            for mafia in list(filter(lambda x: Roles.LOVER not in x.abr, self.get_who_mafia)):
                                if mafia.client.id == killed.client.id:
                                    mafia.role_action(random.choice(self.get_who_civs).client.id, self.room_id)
                                else:
                                    mafia.role_action(killed.client.id, self.room_id)
                        except Exception as e:
                            self.log(f"Ошибка при убийстве?????? {e}")
                        try:
                            killing_list = self.get_who_journalist_may_check()[:2]
                            journalist = self.get_who_journalist()
                            if journalist and killing_list:
                                journalist = journalist[0]
                                for checkering in killing_list:
                                    for ind, player in enumerate(self.players):
                                        if player.email == checkering.email:
                                            self.players[ind].abr.append(Roles.JOURNALIST)
                                            
                                    journalist.role_action(checkering.client.id, self.room_id)
                        except Exception as e:
                            self.log(f"!!! Ошибка при журе?????? {e}")
                        time.sleep(.2)
                        try:
                            checked_list = self.get_who_sheriff_may_check()
                            sheriff = self.get_who_sheriff()
                            if checked_list and sheriff:
                                sheriff = sheriff[0]
                                checked = random.choice(checked_list)
                                for ind, player in enumerate(self.players):
                                    if player.email == checked.email:
                                        self.players[ind].abr.append(Roles.SHERIFF)
                                
                                sheriff.role_action(checked.client.id, self.room_id)
                                self.log(f"Чекнул {checked.get_nickname()}")
                        except Exception as e:
                            self.log(f"!!! Ошибка при чеке?????? {e}")
                        try:
                            checked_list = self.get_who_doctor_may_health()
                            doctors = self.get_who_doctor()
                            for doctor in doctors:
                                checked = random.choice(checked_list)
                                doctor.role_action(checked.client.id, self.room_id)
                                self.log(f"Вылечил {checked.get_nickname()}")
                        except Exception as e:
                            self.log(f"!!! Ошибка при лечение?????? {e}")
                    elif message["t"] == 8:
                        self.log("Дневное гс")
                        
                        terr = self.get_who_terrorist()
                        boomeds = self.get_who_terrorist_may_boom()
                        ignore = []
                        print(terr)
                        print(boomeds)
                        if terr and boomeds:
                            boomed = random.choice(boomeds)
                            ignore = [terr[0].client.id, boomed.client.id]
                            terr[0].role_action(boomed.client.id, self.room_id)
                            time.sleep(.4)
                            
                            
                        who_may_killed = list(filter(lambda x: x.client.id not in ignore, self.get_who_civ_may_kill()))
                        if who_may_killed:
                            who_killed = random.choice(who_may_killed)
                            for player in list(filter(lambda x: Roles.LOVER not in x.abr, self.sorted_players())):
                                try:
                                    if player.client.id == who_killed.client.id:
                                        player.role_action(random.choice(self.get_who_civ_may_kill(player.role)).client.id, self.room_id)
                                    else:
                                        player.role_action(who_killed.client.id, self.room_id)
                                    time.sleep(.5)
                                    if player.client != listener_account:
                                        player.disconn = True
                                        player.client.__del__()
                                except:
                                    pass
                elif data_type == "empty":
                    if not last_empty_packet_time:
                        last_empty_packet_time = time.time()
                    else:
                        if (time.time() - last_empty_packet_time) > 5:
                            self.log("ХАРД СБОЙ... меняем хоста")
                            try:
                                listener_account = self.get_listener(listener_account).client
                            except:
                                self.log("не удалось поменять хоста", True)
                                self.rehost(hard=True)
                                stopers += 1
                                break
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
                            #last_empty_packet_time = 0
                            #stopers+=1
                            #self.rehost(hard=True)
                elif not data_type:
                    last_empty_packet_time = 0
                    if data.get("t") and not int(data["t"]) % 10:
                        for index, player in enumerate(self.players):
                            if player.disconn:
                                continue
                            try:
                                player.client.client_socket.send("p\n".encode())
                            except Exception as e:
                                self.log(f"отвалился аккаунт {player.get_nickname()} НАХУЙ!")
                                self.players[index].disconn = True
                                size_disabled_accounts = len(self.disconn_players)
                                self.log(size_disabled_accounts)
                                    

                                if size_disabled_accounts > 5:
                                    stopers += 1
                                    self.rehost(hard=True)
                                    break
                        #self.log(f">> [⌚] {data.get('t')}")
if __name__ == "__main__":
    farm = Farm()
    farm.start()
