import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from loguru import logger


load_dotenv()

DIR_SKAN = os.getenv("DIR_SKAN")

INTERVAL_SYNCHRONISATION_MINUTES = int(os.getenv("INTERVAL_SYNCHRONISATION_MINUTES"))


def check_folder_and_execution_of_works(dir_skan, cloud):
    """Проверяет нахождение новых файлов в указанной директории и создает копии в облачном хранилище или удаляет лишние файлы в облачном хранилище."""
    logger.info(f"Проверка директории {dir_skan} на наличие новых файлов или удаление лишних файлов в облачном хранилище.")
    if not os.path.exists(dir_skan):
        logger.error(f"Директория {dir_skan} не найдена.")
        return
    subdir = os.path.relpath(dir_skan, DIR_SKAN) if dir_skan != DIR_SKAN else None

    all_entries = os.listdir(dir_skan)
    dirs_only = [f for f in all_entries if os.path.isdir(os.path.join(dir_skan, f))]
    files_only = [f for f in all_entries if os.path.isfile(os.path.join(dir_skan, f))]

    os_files_info = [
        {
            'name': f,
            'updated': os.path.getmtime(os.path.join(dir_skan, f))
        }
        for f in files_only
        if '.' in f and not f.startswith('.')
    ]
    logger.info(f"Получение информации о файлах в облачном хранилище.")
    cloud_response = cloud.get_in_dir(subdir) or []

    cloud_files = [
        f for f in cloud_response
        if '.' in f['name'] and not f['name'].startswith('.')
    ]
    cloud_folders = [
        d for d in cloud_response
        if '.' not in d['name'] and not d['name'].startswith('.')
    ]
    cloud_folders_set = set()

    dirs_only_set = set()

    for dir_only in dirs_only:
        dirs_only_set.add(dir_only)

    for cloud_file in cloud_folders:
        cloud_folders_set.add(cloud_file['name'])

    folder_only = dirs_only_set != cloud_folders_set
    if folder_only:
        folders_cloud_delete = [folder
                              for folder in cloud_folders_set - dirs_only_set
                              if len(cloud_folders_set) > len(dirs_only_set)
                              ]
        for folder in folders_cloud_delete:
            cloud.delete_folder_iterative(subdir + '/' + folder if subdir is not None else '' + folder)

    local_files_map = {f['name']: f['updated'] for f in os_files_info}  # timestamp
    cloud_files_map = {f['name']: datetime.fromisoformat(f['updated']).timestamp()
                       for f in cloud_files}  # Конвертируем в timestamp

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

    local_only = set(local_files_map) - set(cloud_files_map)
    if local_only:
        logger.info(f"Найдены новые файлы в директории {dir_skan}: {local_only}")
        for file_name in local_only:
            logger.info(f"Загрузка файла {file_name} в облако из локальной папки {dir_skan}")
            upload = cloud.upload_to_cloud(os.path.join(dir_skan, file_name), file_name, subdir)
            if upload:
                logger.info(f"Файл {file_name} успешно загружен в облако")

    cloud_only = set(cloud_files_map) - set(local_files_map)
    if cloud_only:
        logger.info(f"Найдены удаленные файлы в директории {dir_skan}: {cloud_only}")
        for file_name in cloud_only:
            cloud.delete_file_from_cloud(file_name, subdir)


    if time_diffs:
        logger.info(f"Найдены обновленные файлы в директории {dir_skan}: {time_diffs}")
        for file_name in time_diffs:
            logger.info(f"Обновление файла {file_name['name']} в облако из локальной папки {dir_skan}")
            upload = cloud.upload_to_cloud(os.path.join(dir_skan, file_name['name']), file_name['name'], subdir)
            if upload:
                logger.info(f"Файл {file_name['name']} успешно обновлен в облаке")

    for dir_name in dirs_only:
        check_folder_and_execution_of_works(os.path.join(dir_skan, dir_name), cloud)


class CloudController:
    def __init__(self, api_key, path):
        """Инициализирует объект класса CloudController с ключом API и путем к папке."""
        self.url = "https://cloud-api.yandex.net/v1/disk/resources"
        self.headers = {'Authorization': f'OAuth {api_key}'}
        self.path = path


    def get_in_dir(self, subdir=None):
        """Получает список содержимого папки в облаке по заданному пути."""
        params = {
            "path": f"/{self.path}",
            "limit": 1000,
            "sort": "name",
        }
        if subdir is not None:
            params['path'] = f'/{self.path}/{subdir}'
        response = requests.get(self.url, headers=self.headers, params=params)
        if response.status_code == 200:
            logger.info(f"Содержимое облачного хранилища по пути {params['path']} успешно получен")
            data = response.json()
            data = data["_embedded"]["items"]
            response = []
            for item in data:
                response.append({'name': item['name'], 'updated': item['modified']})
            return response
        elif response.status_code == 404 and response.json()['error'] == 'DiskNotFoundError':
            logger.info(f"Папка отсутствует, создание папки в облаке.")
            self.create_folder_in_cloud(subdir)
        else:
            logger.error(f"Ошибка при получении содержимого папки {params['path']}: \n Статус код: {response.status_code} \n Описание ошибки: {response.json()}")


    def upload_to_cloud(self, file_path, filename, subdir=None):
        """Загружает файл в облако по указанному пути и имени файла."""
        url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
        params = {
            "path": f"/{self.path}/{filename}",
            "overwrite": True
        }
        if subdir is not None:
            params['path'] = f'/{self.path}/{subdir}/{filename}'

        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 200:
            logger.info(f"Получена ссылка для загрузки файла в облако.")
        elif response.status_code == 409:
            logger.error(f"Папка отсутствует, создание папки в облаке.")
            if self.create_folder_in_cloud(subdir):
                logger.info("Папка создана успешно")
                self.upload_to_cloud(file_path, filename, subdir)
                return True
        else:
            logger.error(f"Ошибка при получении ссылки для загрузки файла: \n Статус код: {response.status_code} \n Описание ошибки: {response.json()}")

        upload_href = response.json()["href"]

        with open(file_path, "rb") as file:
            upload_response = requests.put(upload_href, files={"file": file})

        if upload_response.status_code != 201:
            logger.error(f"Ошибка при загрузке файла: {file_path} в облако: \n Статус код: {upload_response.status_code} \n Описание ошибки: {upload_response.json()}")
            return

        return True


    def delete_file_from_cloud(self, filename, subdir=None):
        """Удаляет файл из облака по указанному пути и имени файла."""
        params = {
            "path": f"/{self.path}/{filename}",
            "permanently": True
        }
        if subdir is not None:
            params['path'] = f'/{self.path}/{subdir}/{filename}'

        logger.info(f"Удаление файла {filename} из облачного хранилища по пути {params['path']}.")
        response = requests.delete(self.url, headers=self.headers, params=params)

        if response.status_code == 204:
            logger.info(f"Файл {filename} успешно удален из облака")
        else:
            logger.error(f"Ошибка при удалении файла: {filename} из облачного хранилища по пути {params['path']}: \n Статус код: {response.status_code} \n Описание ошибки: {response.json()}")


    def create_folder_in_cloud(self, subdir=None):
        """Создает папку в облаке по указанному пути."""
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


    def get_folder_contents(self, folder_path):
        """Получает список содержимого папки"""

        params = {
            "path": f'{self.path}/{folder_path}',
            "limit": 1000,
            "sort": "name"
        }
        logger.info(f"Получение списка содержимого облачного хранилища по пути: {params['path']}.")
        try:
            response = requests.get(self.url, headers=self.headers, params=params)
            if response.status_code == 200:
                logger.info(f"Содержимое облачного хранилища по пути {params['path']} успешно получен")
                return response.json().get('_embedded', {}).get('items', [])
            else:
                logger.error(f"Ошибка при получении списка содержимого облачного хранилища по пути {params['path']}: \n Статус код: {response.status_code} \n Описание ошибки: {response.json()}")
            return []
        except requests.exceptions.RequestException:
            logger.error(f"Ошибка при получении списка содержимого облачного хранилища по пути {params['path']}: {requests.exceptions.RequestException}")
            return []


    def delete_single_folder(self, folder_path):
        """Удаляет пустую папку"""
        params = {"path": f'{self.path}/{folder_path}', "permanently": "true"}
        logger.info(f"Удаление папки {params['path']} из облачного хранилища.")
        response = requests.delete(self.url, headers=self.headers, params=params)
        if response.status_code == 204:
            logger.info(f"Папка {params['path']} успешно удалена")
            return True
        else:
            logger.error(f"Ошибка при удалении папки: {params['path']}: \n Статус код: {response.status_code} \n Описание ошибки: {response.json()}")


    def delete_folder_iterative(self, folder_path):
        """Итеративное удаление с использованием стека"""
        stack = [folder_path]
        deleted_items = set()


        while stack:
            current_path = stack.pop()

            # Получаем содержимое текущей папки
            contents = self.get_folder_contents(current_path)


            if not contents:
                # Если папка пуста - удаляем её
                if self.delete_single_folder(current_path):
                    deleted_items.add(current_path)
                continue

            # Добавляем текущую папку обратно в стек
            stack.append(current_path)

            # Добавляем все элементы папки в стек
            for item in contents:
                if item['path'] not in deleted_items:
                    path_list = ['/'+i for i in item['path'].split('/')[2:]]
                    path = ''.join(path_list)
                    self.delete_file_from_cloud(path[1:])

        return True