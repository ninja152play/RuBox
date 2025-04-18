import os
from time import sleep
from dotenv import load_dotenv
from handlers import CloudController, check_folder_and_execution_of_works, INTERVAL_SYNCHRONISATION_MINUTES

load_dotenv()

API_KEY = os.getenv("API_KEY")

DIR_SKAN = os.getenv("DIR_SKAN")

DISK_DIR = os.getenv("DISK_DIR")

cloud = CloudController(API_KEY, DISK_DIR)

while True:
    check_folder_and_execution_of_works(DIR_SKAN, cloud)
    sleep(INTERVAL_SYNCHRONISATION_MINUTES * 60)



