import tkinter as tk
from tkinter import ttk
from loader import main

from handlers import CloudController, check_folder_and_execution_of_works, INTERVAL_SYNCHRONISATION_MINUTES


class RuBoxApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RuBox")
        self.setup_ui()

    def setup_ui(self):
        ttk.Label(self.root, text="Вставьте ваш API_KEY").pack(pady=5)
        self.api_key = ttk.Entry(self.root, width=40)
        self.api_key.pack(pady=5)

        ttk.Label(self.root, text="Введите вашу локальную директорию").pack(pady=5)
        self.local_dir = ttk.Entry(self.root, width=40)
        self.local_dir.pack(pady=5)

        ttk.Label(self.root, text="Введите вашу директорию в облаке").pack(pady=5)
        ttk.Label(self.root,
                  text="Пример: https://disk.yandex.ru/client/disk/Save/test → указывать только Save/test").pack(pady=5)
        self.cloud_dir = ttk.Entry(self.root, width=40)
        self.cloud_dir.pack(pady=5)

        ttk.Label(self.root, text="Введите интервал синхронизации в минутах").pack(pady=5)
        self.minutes = ttk.Entry(self.root, width=40)
        self.minutes.pack(pady=5)

        ttk.Label(self.root, text="Введите путь к логу (если не указать, то лог будет в корне проекта)").pack(pady=5)
        self.log = ttk.Entry(self.root, width=40)
        self.log.pack(pady=5)

        # Кнопки
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Start", command=self.on_start).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save settings", command=self.on_save).pack(side=tk.LEFT, padx=5)

    def on_start(self):
        self.root.destroy()
        main(CloudController, check_folder_and_execution_of_works, INTERVAL_SYNCHRONISATION_MINUTES)



    def on_save(self):
        with open(".env", "r") as f:
            lines = f.readlines()
            for line in lines:
                if "API_KEY=" in line:
                    self.api_key = (line.split("=")[1]).strip()
                elif "DIR_SKAN=" in line:
                    self.local_dir = (line.split("=")[1]).strip()
                elif "DISK_DIR=" in line:
                    self.cloud_dir = (line.split("=")[1]).strip()
                elif "INTERVAL_SYNCHRONISATION_MINUTES=" in line:
                    self.minutes = (line.split("=")[1]).strip()
                elif "LOG_FILE_PATH=" in line:
                    self.log = (line.split("=")[1]).strip()
        with open(".env", "w") as f:
            print(self.api_key)
            if not isinstance(self.api_key, str):
                f.write(f"API_KEY={self.api_key.get()}\n")
            else:
                f.write(f"API_KEY={self.api_key}\n")
            if not isinstance(self.local_dir, str):
                f.write(f"DIR_SKAN={self.local_dir.get()}\n")
            else:
                f.write(f"DIR_SKAN={self.local_dir}\n")
            if not isinstance(self.cloud_dir, str):
                f.write(f"DISK_DIR={self.cloud_dir.get()}\n")
            else:
                f.write(f"DISK_DIR={self.cloud_dir}\n")
            if not isinstance(self.minutes, str):
                f.write(f"INTERVAL_SYNCHRONISATION_MINUTES={self.minutes.get()}\n")
            else:
                f.write(f"INTERVAL_SYNCHRONISATION_MINUTES={self.minutes}\n")
            if not isinstance(self.log, str):
                f.write(f"LOG_FILE_PATH={self.log.get()}\n")
            else:
                f.write(f"LOG_FILE_PATH={self.log}\n")
        print("Настройки сохранены в .env")


def gui():
    root = tk.Tk()
    app = RuBoxApp(root)
    root.mainloop()