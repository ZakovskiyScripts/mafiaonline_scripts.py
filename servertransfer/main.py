import json
import time
from mafiaonline.mafiaonline import Client
from typing import List

config = input("config << ")
if not config:
    config = "default"
with open(f"./configs/{config}.json", "r") as cfg:
    config = json.load(cfg)
DEBUG: bool = config['debug']
ACCOUNTS = config['accounts']
SERVER = config['server']

class TransferServer:
    def __init__(self):
        self.accounts = []
        self.from_file()
        self.start()

    def from_file(self):
        """
        Это файл с данными от аккаунтов в формате '''email:password'''
        """
        for account in ACCOUNTS:
            data = account.split(":")
            self.accounts.append([data[0], data[1]])

    def start(self):
        for account in self.accounts:
            client = Client(debug=DEBUG)
            client.sign_in(account[0], account[1])
            client.select_language(SERVER)
            client.__del__()
            print(f"сменили у {account[0]}")
            time.sleep(.2)


if __name__ == "__main__":
    farm = TransferServer()   
