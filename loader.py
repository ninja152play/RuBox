import os
from time import sleep
from dotenv import load_dotenv
from loger import init_logger


def main(CloudController, check_folder_and_execution_of_works, INTERVAL_SYNCHRONISATION_MINUTES):
    load_dotenv()

    API_KEY = os.getenv("API_KEY")

    DIR_SKAN = os.getenv("DIR_SKAN")

    DISK_DIR = os.getenv("DISK_DIR")

    LOG_FILE_PATH = os.getenv("LOG_FILE_PATH")

    if LOG_FILE_PATH:
        LOG_FILE_PATH = LOG_FILE_PATH + "/RuBox.log"
    else:
        LOG_FILE_PATH = "RuBox.log"

    init_logger(LOG_FILE_PATH)

    cloud = CloudController(API_KEY, DISK_DIR)

    while True:
        check_folder_and_execution_of_works(DIR_SKAN, cloud)
        sleep(INTERVAL_SYNCHRONISATION_MINUTES * 60)