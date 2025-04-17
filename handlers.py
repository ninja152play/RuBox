import requests
import os
import json
from dotenv import load_dotenv
from datetime import datetime, timezone


load_dotenv()

DIR_SKAN = os.getenv("DIR_SKAN")

INTERVAL_SYNCHRONISATION_MINUTES = int(os.getenv("INTERVAL_SYNCHRONISATION_MINUTES"))


def check_folder_and_execution_of_works(dir_skan, cloud):
    subdir = os.path.relpath(dir_skan, DIR_SKAN) if dir_skan != DIR_SKAN else None

    # Получаем списки файлов и папок
    all_entries = os.listdir(dir_skan)
    dirs_only = [f for f in all_entries if os.path.isdir(os.path.join(dir_skan, f))]
    files_only = [f for f in all_entries if os.path.isfile(os.path.join(dir_skan, f))]

    # Формируем информацию о локальных файлах (храним timestamp)
    os_files_info = [
        {
            'name': f,
            'updated': os.path.getmtime(os.path.join(dir_skan, f))  # Сохраняем timestamp
        }
        for f in files_only
        if '.' in f and not f.startswith('.')
    ]

    # Получаем данные из облака
    cloud_files = cloud.get_in_dir(subdir) or []
    cloud_files = [
        f for f in cloud_files
        if '.' in f['name'] and not f['name'].startswith('.')
    ]

    # Создаем словари для быстрого поиска
    local_files_map = {f['name']: f['updated'] for f in os_files_info}  # timestamp
    cloud_files_map = {f['name']: datetime.fromisoformat(f['updated']).timestamp()
                       for f in cloud_files}  # Конвертируем в timestamp

    # Находим расхождения
    common_files = set(local_files_map) & set(cloud_files_map)
    time_diffs = [
        {
            'name': name,
            'local': datetime.fromtimestamp(local_files_map[name], tz=timezone.utc)
            .replace(microsecond=0).isoformat(),
            'cloud': datetime.fromtimestamp(cloud_files_map[name], tz=timezone.utc)
            .replace(microsecond=0).isoformat(),
            'diff_min': round(abs(local_files_map[name] - cloud_files_map[name]) / 60, 2)
        }
        for name in common_files
        if abs(local_files_map[name] - cloud_files_map[name]) > INTERVAL_SYNCHRONISATION_MINUTES * 60 and abs(local_files_map[name] - cloud_files_map[name]) < INTERVAL_SYNCHRONISATION_MINUTES * 60 * 3
    ]

    print(f"Local only: {set(local_files_map) - set(cloud_files_map)}")
    local_only = set(local_files_map) - set(cloud_files_map)
    if local_only:
        for file_name in local_only:
            print(f"Загрузка файла {file_name} в облако из локальной папки {dir_skan}")
            upload = cloud.upload_to_cloud(os.path.join(dir_skan, file_name), file_name, subdir)
            if upload:
                print(f"Файл {file_name} успешно загружен в облако")

    print(f"Cloud only: {set(cloud_files_map) - set(local_files_map)}")
    cloud_only = set(cloud_files_map) - set(local_files_map)
    if cloud_only:
        for file_name in cloud_only:
            print(f"Удаление файла {file_name} из облака")
            delete = cloud.delete_file_from_cloud(file_name, subdir)
            if delete:
                print(f"Файл {file_name} успешно удален из облака")
    print(f"Time diffs: {time_diffs}")
    if time_diffs:
        for file_name in time_diffs:
            print(f"Обновление файла {file_name['name']} в облако из локальной папки {dir_skan}")
            upload = cloud.upload_to_cloud(os.path.join(dir_skan, file_name['name']), file_name['name'], subdir)
            if upload:
                print(f"Файл {file_name} успешно загружен в облако")


    for dir_name in dirs_only:
        check_folder(os.path.join(dir_skan, dir_name), cloud)


class CloudController:
    def __init__(self, api_key, path):
        self.url = "https://cloud-api.yandex.net/v1/disk/resources"
        self.headers = {'Authorization': f'OAuth {api_key}'}
        self.path = path

    def get_in_dir(self, subdir=None):
        params = {
            "path": f"/{self.path}",
            "limit": 1000,
            "sort": "name",
        }
        if subdir is not None:
            params['path'] = f'/{self.path}/{subdir}'
        response = requests.get(self.url, headers=self.headers, params=params)
        if response.status_code == 200:
            data = response.json()
            data = data["_embedded"]["items"]
            response = []
            for item in data:
                response.append({'name': item['name'], 'updated': item['modified']})
            return response

    def upload_to_cloud(self, file_path, filename, subdir=None):
        url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
        params = {
            "path": f"/{self.path}/{filename}",
            "overwrite": True
        }
        if subdir is not None:
            params['path'] = f'/{self.path}/{subdir}/{filename}'

        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 200:
            pass
        elif response.status_code == 409:
            print("Папка не существует, создание папки в облаке")
            if self.create_folder_in_cloud(subdir):
                print("Папка создана успешно")
                self.upload_to_cloud(file_path, filename, subdir)
                return True
        else:
            print(f"Ошибка при загрузке файла: {filename}")

        upload_href = response.json()["href"]

        with open(file_path, "rb") as file:
            upload_response = requests.put(upload_href, files={"file": file})

        if upload_response.status_code != 201:
            raise Exception("Ошибка при загрузке файла в облако")

        return True

    def delete_file_from_cloud(self, filename, subdir=None):
        params = {
            "path": f"/{self.path}/{filename}",
            "permanently": True
        }
        if subdir is not None:
            params['path'] = f'/{self.path}/{subdir}/{filename}'

        response = requests.delete(self.url, headers=self.headers, params=params)

        if response.status_code == 204:
            return True
        else:
            print(f"Ошибка при удалении файла: {filename}")

    def create_folder_in_cloud(self, subdir=None):
        params = {
            "path": f"/{self.path}/{subdir}",
        }
        if subdir is not None:
            params['path'] = f'/{self.path}/{subdir}'

        response = requests.put(self.url, headers=self.headers, params=params)

        if response.status_code != 201:
            print(f"Ошибка при создании папки: {subdir}")
        else:
            return True
