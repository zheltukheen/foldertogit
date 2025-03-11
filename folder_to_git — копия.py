#!/usr/bin/env python3
"""
Folder to Git - Утилита для преобразования папок с версиями в Git-репозиторий

Этот скрипт позволяет создать Git-репозиторий из набора папок, 
содержащих разные версии проекта. Скрипт определяет версии из имен папок,
сортирует их и создает коммиты в хронологическом порядке.

Использование:
    python folder_to_git.py --source /путь/к/папкам/с/версиями --target /путь/к/репозиторию
                         [--pattern "версия_*"] [--extract-pattern "[0-9]+"]
                         [--authors-file authors.txt]

Примеры:
    python folder_to_git.py --source ./versions --target ./project_repo
    python folder_to_git.py --source ./my_project --target ./git_repo --pattern "project_v*"
    python folder_to_git.py --source ./app --target ./repo --extract-pattern "v([0-9]+)"
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import argparse
import logging
import time
from datetime import datetime
from pathlib import Path
import glob
import fnmatch


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("folder_to_git.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def parse_args():
    """Разбор аргументов командной строки"""
    parser = argparse.ArgumentParser(description='Создание Git-репозитория из папок с версиями проекта')
    parser.add_argument('--source', '-s', dest='source_dir', default='.',
                        help='Исходная директория с папками версий')
    parser.add_argument('--target', '-t', dest='target_dir', default='git_history',
                        help='Путь для создания Git-репозитория')
    parser.add_argument('--pattern', '-p', default='*',
                        help='Шаблон для поиска папок с версиями')
    parser.add_argument('--extract-pattern', '-e', default='[0-9]+(\.[0-9]+)?',
                        help='Регулярное выражение для извлечения номера версии')
    parser.add_argument('--dry-run', '-d', action='store_true',
                        help='Тестовый режим без создания репозитория')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Подробный вывод')
    parser.add_argument('--authors-file', '-a', 
                        help='Файл с сопоставлением версий и авторов (формат: версия:имя:email)')
    parser.add_argument('--message-template', '-m',
                        help='Шаблон сообщения коммита. Доступные переменные: {version}, {folder}, {date}, {files}, {author}')
    parser.add_argument('--author', default='Developer',
                        help='Имя автора коммита')
    parser.add_argument('--email', default='dev@example.com',
                        help='Email автора коммита')
    parser.add_argument('--append', action='store_true',
                        help='Добавить новые версии в существующий репозиторий без его инициализации')
    return parser.parse_args()


def run_command(cmd, cwd=None, check=True, capture_output=True):
    """Выполняет команду и возвращает результат"""
    try:
        if capture_output:
            result = subprocess.run(
                cmd, 
                cwd=cwd, 
                check=check, 
                capture_output=True, 
                text=True
            )
            return result
        else:
            result = subprocess.run(
                cmd, 
                cwd=cwd, 
                check=check
            )
            return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка выполнения команды: {' '.join(cmd)}")
        logger.error(f"Код выхода: {e.returncode}")
        if e.stdout:
            logger.error(f"Вывод: {e.stdout}")
        if e.stderr:
            logger.error(f"Ошибка: {e.stderr}")
        if check:
            raise
        return e


def extract_version_number(folder_name, extract_pattern):
    """Извлекает номер версии из имени папки с помощью регулярного выражения"""
    match = re.search(extract_pattern, folder_name)
    if match:
        return match.group()
    return "[WARN]"  # Используем [WARN] вместо None для соответствия shell-скрипту


def get_folder_creation_time(folder_path):
    """Получение времени создания папки с использованием интеллектуального анализа файлов"""
    try:
        # Структуры для хранения времени файлов
        file_times = []
        key_file_times = []  # Времена ключевых файлов
        
        # Список шаблонов ключевых файлов, которые обычно меняются при обновлении версии
        key_file_patterns = [
            "version.py", "version.txt", "VERSION", 
            "main.py", "app.py", "bot.py", "config.py", 
            "requirements.txt", "setup.py",
            "Dockerfile", "docker-compose.yml"
        ]
        
        # Счетчик для лимита обработанных файлов
        processed_files = 0
        max_files = 500  # Ограничение на количество обрабатываемых файлов для производительности
        
        # Рекурсивный обход директорий
        for root, dirs, files in os.walk(folder_path):
            # Пропускаем служебные директории
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'venv', 'env', '.venv']]
            
            # Ограничение на количество файлов
            if processed_files >= max_files:
                break
            
            for file in files:
                # Пропускаем служебные файлы
                if file.startswith('.') or file.endswith('.pyc') or file in ['.DS_Store', '.gitignore']:
                    continue
                
                file_path = os.path.join(root, file)
                
                try:
                    # Получаем время изменения файла
                    file_time = os.path.getmtime(file_path)
                    
                    # Добавляем время в общий список
                    file_times.append(file_time)
                    
                    # Проверяем, является ли файл ключевым
                    is_key_file = False
                    for pattern in key_file_patterns:
                        if pattern in file.lower():
                            key_file_times.append(file_time)
                            is_key_file = True
                            break
                    
                    processed_files += 1
                except (FileNotFoundError, PermissionError) as e:
                    pass  # Игнорируем файлы, к которым нет доступа
        
        # Если файлы не найдены, используем время создания самой папки
        if not file_times:
            try:
                folder_time = os.path.getctime(folder_path)
                logging.warning(f"Не найдены файлы в папке {folder_path}, используется время создания папки: {datetime.fromtimestamp(folder_time)}")
                return folder_time
            except Exception as e:
                logging.error(f"Ошибка при получении времени создания папки {folder_path}: {e}")
                # Возвращаем текущую дату как запасной вариант
                return time.time()
        
        # Если найдены ключевые файлы, приоритизируем их
        if key_file_times:
            # Вычисляем медиану времен ключевых файлов
            key_file_times.sort()
            if len(key_file_times) % 2 == 0:
                median_time = (key_file_times[len(key_file_times)//2] + key_file_times[len(key_file_times)//2 - 1]) / 2
            else:
                median_time = key_file_times[len(key_file_times)//2]
                
            logging.debug(f"Использована медиана времен ключевых файлов для {folder_path}: {datetime.fromtimestamp(median_time)}")
            return median_time
        else:
            # Вычисляем медиану времен всех файлов
            file_times.sort()
            if len(file_times) % 2 == 0:
                median_time = (file_times[len(file_times)//2] + file_times[len(file_times)//2 - 1]) / 2
            else:
                median_time = file_times[len(file_times)//2]
                
            logging.debug(f"Использована медиана времен всех файлов для {folder_path}: {datetime.fromtimestamp(median_time)}")
            return median_time
                
    except Exception as e:
        logging.error(f"Ошибка при анализе папки {folder_path}: {e}")
        # Возвращаем текущую дату как запасной вариант
        return time.time()


def get_author_info(version, authors_file):
    """Получает информацию об авторе из файла сопоставления"""
    if not authors_file or not os.path.exists(authors_file):
        return None, None
    
    try:
        with open(authors_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(':')
                if len(parts) >= 3 and parts[0] == version:
                    return parts[1], parts[2]
    except Exception as e:
        logger.error(f"Ошибка при чтении файла авторов: {e}")
    
    return None, None


def safe_copy_files(source_folder, target_folder):
    """
    Безопасно копирует файлы из исходной папки в целевую
    
    :param source_folder: Путь к исходной папке
    :param target_folder: Путь к целевой папке
    :return: True если копирование успешно, иначе False
    """
    try:
        # Используем новую функцию copy_files для копирования
        copy_files(source_folder, target_folder, logger)
        return True
    except Exception as e:
        logger.error(f"Ошибка при копировании файлов: {str(e)}")
        return False


def init_git_repo(repo_path):
    """Инициализирует Git-репозиторий в указанной директории"""
    try:
        # Создаем директорию, если она не существует
        os.makedirs(repo_path, exist_ok=True)
        
        # Проверяем, существует ли уже репозиторий
        git_dir = os.path.join(repo_path, '.git')
        if os.path.exists(git_dir) and os.path.isdir(git_dir):
            logging.info(f"Репозиторий уже существует в {repo_path}")
            return True
        
        # Инициализируем новый репозиторий
        logging.info(f"Инициализация репозитория в {repo_path}")
        subprocess.run(['git', 'init'], cwd=repo_path, check=True, 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Настраиваем имя пользователя и email для репозитория
        subprocess.run(['git', 'config', 'user.name', 'Folder to Git Script'], 
                      cwd=repo_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(['git', 'config', 'user.email', 'script@example.com'], 
                      cwd=repo_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        return True
    except Exception as e:
        logging.error(f"Ошибка при инициализации репозитория: {e}")
        return False


def copy_files(source_dir, target_dir):
    """
    Копирует файлы из исходной директории в целевую, игнорируя .git папки и файлы
    
    :param source_dir: Исходная директория
    :param target_dir: Целевая директория
    :return: Количество скопированных файлов
    """
    # Список игнорируемых директорий и файлов
    ignore_dirs = ['.git', '__pycache__', 'venv', '.venv', 'node_modules', '.idea', '.vscode', 'dist', 'build', 'env']
    ignore_file_patterns = ['.DS_Store', '*.pyc', '*.pyo', '*.pyd', '.gitignore', '.gitattributes', '*.swp', '*.swo', '*.log', '*.bak', '*.egg-info']
    
    file_count = 0
    try:
        # Если исходная директория имеет ограниченный доступ, используем альтернативный подход
        if not os.access(source_dir, os.R_OK | os.X_OK):
            logging.warning(f"Ограниченный доступ к директории {source_dir}. Пробуем альтернативный метод копирования.")
            try:
                # Используем системную команду cp с флагом -R для рекурсивного копирования
                # и игнорируя ошибки доступа
                import tempfile
                temp_dir = tempfile.mkdtemp()
                os.system(f'cp -R "{source_dir}"/* "{temp_dir}" 2>/dev/null')
                
                # Теперь копируем из временной директории, исключая игнорируемые файлы
                for root, dirs, files in os.walk(temp_dir):
                    # Исключаем игнорируемые директории
                    for ignore_dir in ignore_dirs:
                        if ignore_dir in dirs:
                            dirs.remove(ignore_dir)
                    
                    # Фильтруем директории 
                    dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pattern) for pattern in ignore_file_patterns)]
                    
                    # Вычисляем относительный путь
                    rel_path = os.path.relpath(root, temp_dir)
                    if rel_path == '.':
                        rel_path = ''
                    
                    # Создаем соответствующие директории в целевой папке
                    if rel_path:
                        os.makedirs(os.path.join(target_dir, rel_path), exist_ok=True)
                    
                    # Копируем файлы, игнорируя игнорируемые файлы
                    for file in files:
                        if any(fnmatch.fnmatch(file, pattern) for pattern in ignore_file_patterns):
                            continue
                        
                        source_file = os.path.join(root, file)
                        if rel_path:
                            target_file = os.path.join(target_dir, rel_path, file)
                        else:
                            target_file = os.path.join(target_dir, file)
                        
                        try:
                            shutil.copy2(source_file, target_file)
                            file_count += 1
                        except (shutil.SameFileError, OSError) as e:
                            logging.warning(f"Ошибка при копировании файла {source_file}: {e}")
                
                # Очищаем временную директорию
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                return file_count
            except Exception as e:
                logging.error(f"Ошибка при альтернативном копировании: {e}")
                # Продолжаем выполнение стандартного метода, если альтернативный не сработал
        
        # Стандартный метод копирования
        for root, dirs, files in os.walk(source_dir, onerror=lambda err: logging.warning(f"Ошибка при обходе директорий: {err}")):
            # Игнорируем директории из списка
            for ignore_dir in ignore_dirs:
                if ignore_dir in dirs:
                    dirs.remove(ignore_dir)
            
            # Фильтруем директории
            dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pattern) for pattern in ignore_file_patterns)]
            
            # Вычисляем относительный путь
            try:
                rel_path = os.path.relpath(root, source_dir)
                if rel_path == '.':
                    rel_path = ''
                
                # Создаем соответствующую структуру директорий в целевой папке
                if rel_path:
                    target_subdir = os.path.join(target_dir, rel_path)
                    os.makedirs(target_subdir, exist_ok=True)
                else:
                    target_subdir = target_dir
                
                # Копируем файлы, игнорируя файлы из списка
                for file in files:
                    # Проверяем, нужно ли игнорировать файл
                    if any(fnmatch.fnmatch(file, pattern) for pattern in ignore_file_patterns):
                        continue
                    
                    source_file = os.path.join(root, file)
                    target_file = os.path.join(target_subdir, file)
                    
                    # Копируем файл, обрабатывая исключения
                    try:
                        shutil.copy2(source_file, target_file)
                        file_count += 1
                    except (shutil.SameFileError, OSError, PermissionError) as e:
                        logging.warning(f"Ошибка при копировании файла {source_file}: {e}")
            except Exception as e:
                logging.warning(f"Ошибка при обработке пути {root}: {e}")
                continue
        
        if file_count == 0:
            logging.warning(f"Не найдено файлов для копирования из {source_dir}. Это может быть из-за прав доступа или фильтров игнорирования.")
            # Попробуем альтернативный метод копирования через системную команду
            try:
                import tempfile
                temp_dir = tempfile.mkdtemp()
                os.system(f'cp -R "{source_dir}"/* "{temp_dir}" 2>/dev/null')
                
                if os.listdir(temp_dir):
                    logging.info(f"Найдены файлы при альтернативном копировании. Копируем их в целевую директорию.")
                    os.system(f'cp -R "{temp_dir}"/* "{target_dir}" 2>/dev/null')
                    
                    # Подсчитываем примерное количество скопированных файлов
                    for _, _, files in os.walk(target_dir):
                        file_count += len(files)
                
                # Очищаем временную директорию
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logging.error(f"Ошибка при альтернативном копировании: {e}")
        
        return file_count
    except Exception as e:
        logging.error(f"Ошибка при копировании файлов: {e}")
        import traceback
        logging.error(f"Трассировка стека:\n{traceback.format_exc()}")
        return file_count


def create_commit(repo_path, version, folder_name, creation_time, file_count,
                author_name="Developer", author_email="dev@example.com", msg_template=None):
    """
    Создает коммит в репозитории с указанной датой и автором
    
    :param repo_path: Путь к репозиторию
    :param version: Номер версии
    :param folder_name: Имя папки с версией
    :param creation_time: Время создания (unix timestamp)
    :param file_count: Количество файлов в версии
    :param author_name: Имя автора
    :param author_email: Email автора
    :param msg_template: Шаблон сообщения коммита
    :return: True если коммит создан успешно, иначе False
    """
    try:
        # Форматируем дату создания для коммита и сообщения
        creation_date_iso = datetime.fromtimestamp(creation_time).strftime('%Y-%m-%dT%H:%M:%S')
        creation_date_readable = datetime.fromtimestamp(creation_time).strftime('%Y-%m-%d %H:%M:%S')
        
        # Формируем сообщение коммита
        if msg_template:
            commit_msg = msg_template.format(
                version=version,
                folder=folder_name,
                date=creation_date_readable,
                files=file_count,
                author=author_name
            )
        else:
            commit_msg = f"Version {version}: {folder_name} (created: {creation_date_readable})"
        
        # Проверка наличия файлов для коммита
        logging.info(f"Проверяем директорию {repo_path} на наличие файлов для коммита...")
        has_files = False
        for _, _, files in os.walk(repo_path):
            if files:
                has_files = True
                break
        
        if not has_files:
            logging.warning(f"В репозитории не найдено файлов для коммита версии {version}. Проверьте права доступа и фильтры игнорирования.")
            return False
            
        # Проверка, есть ли изменения для коммита 
        status_cmd = ["git", "status", "--porcelain"]
        try:
            status_output = subprocess.check_output(status_cmd, cwd=repo_path, text=True)
            if not status_output.strip():
                logging.warning(f"Нет изменений для коммита версии {version}")
                # Создаем пустой коммит, чтобы зафиксировать версию
                logging.info(f"Создаем пустой коммит для версии {version}")
                commit_command = [
                    "git", "commit", 
                    "--allow-empty",
                    "-m", commit_msg, 
                    "--author", f"{author_name} <{author_email}>"
                ]
                env = os.environ.copy()
                env["GIT_AUTHOR_DATE"] = creation_date_iso
                env["GIT_COMMITTER_DATE"] = creation_date_iso
                
                subprocess.run(commit_command, cwd=repo_path, check=True, capture_output=True, text=True, env=env)
                return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Ошибка при проверке статуса Git: {e}")
        
        # Добавляем все файлы в индекс
        add_command = ["git", "add", "."]
        add_result = run_git_command(add_command, repo_path)
        
        if not add_result:
            # Попробуем добавить файлы по одному, если возникла ошибка с добавлением всех сразу
            logging.warning("Ошибка при добавлении всех файлов. Пробуем добавлять файлы по одному.")
            for root, dirs, files in os.walk(repo_path):
                # Пропускаем .git директорию
                if '.git' in dirs:
                    dirs.remove('.git')
                
                for file in files:
                    file_path = os.path.relpath(os.path.join(root, file), repo_path)
                    # Экранируем специальные символы в пути файла
                    safe_path = file_path.replace("!", "\\!").replace(" ", "\\ ")
                    try:
                        add_file_command = ["git", "add", safe_path]
                        add_file_result = run_git_command(add_file_command, repo_path)
                        if not add_file_result:
                            logging.warning(f"Не удалось добавить файл {file_path}, пробуем альтернативный метод")
                            # Альтернативный метод - выполняем команду через shell
                            shell_cmd = f"cd {repo_path} && git add \"{file_path}\""
                            os.system(shell_cmd)
                    except Exception as e:
                        logging.error(f"Ошибка при добавлении файла {file_path}: {e}")
        
        # Устанавливаем переменные окружения для даты коммита
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = creation_date_iso
        env["GIT_COMMITTER_DATE"] = creation_date_iso
        
        # Создаем коммит
        commit_command = [
            "git", "commit", 
            "-m", commit_msg, 
            "--author", f"{author_name} <{author_email}>"
        ]
        
        try:
            result = subprocess.run(
                commit_command,
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
                env=env
            )
            logging.debug(f"Коммит создан: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            # Проверяем, есть ли изменения для коммита
            if "nothing to commit" in e.stderr:
                logging.warning("Нет изменений для коммита, пробуем создать пустой коммит")
                try:
                    # Создаем пустой коммит
                    empty_commit_cmd = [
                        "git", "commit", 
                        "--allow-empty",
                        "-m", commit_msg, 
                        "--author", f"{author_name} <{author_email}>"
                    ]
                    subprocess.run(empty_commit_cmd, cwd=repo_path, check=True, env=env, capture_output=True, text=True)
                    return True
                except Exception as ec:
                    logging.error(f"Ошибка при создании пустого коммита: {ec}")
                    return False
            else:
                logging.error(f"Ошибка при создании коммита: {e.stderr}")
                return False
    
    except Exception as e:
        logging.error(f"Ошибка при создании коммита для версии {version}: {e}")
        # Вывод стека вызовов для отладки
        import traceback
        logging.error(f"Трассировка стека:\n{traceback.format_exc()}")
        return False


def migrate_folders_to_git(source_dir, target_dir, folders, dry_run=False, 
                      author_name="Developer", author_email="dev@example.com", 
                      msg_template=None, append_mode=False):
    """Миграция папок с версиями в Git-репозиторий"""
    if dry_run:
        logging.info("Запущен тестовый режим (dry-run), Git-репозиторий не будет создан")
        return True

    # Создаем или проверяем репозиторий
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        logging.info(f"Создана директория для репозитория: {target_dir}")
    
    # Проверяем, существует ли уже Git-репозиторий
    git_dir = os.path.join(target_dir, ".git")
    repo_exists = os.path.exists(git_dir) and os.path.isdir(git_dir)
    
    # Инициализируем репозиторий, только если его нет и не в режиме добавления
    if not repo_exists and not append_mode:
        logging.info(f"Инициализация Git-репозитория в {target_dir}")
        if not run_git_command(["git", "init"], target_dir):
            logging.error("Не удалось инициализировать Git-репозиторий")
            return False
    elif append_mode and not repo_exists:
        logging.error("Ошибка: указан режим --append, но репозиторий не существует в указанной директории")
        return False
    elif append_mode:
        logging.info(f"Добавление новых версий в существующий репозиторий в {target_dir}")
    
    # Проверяем наличие уже созданных коммитов, если используется режим добавления
    existing_versions = set()
    if append_mode:
        try:
            # Получаем список коммитов и извлекаем номера версий из сообщений
            git_log = subprocess.check_output(
                ["git", "log", "--pretty=format:%s"], 
                cwd=target_dir, text=True
            ).splitlines()
            
            for commit_msg in git_log:
                # Извлекаем номер версии из сообщения коммита
                if "Version" in commit_msg and ":" in commit_msg:
                    version_str = commit_msg.split("Version ")[1].split(":")[0].strip()
                    try:
                        version_num = float(version_str) if "." in version_str else int(version_str)
                        existing_versions.add(version_num)
                    except ValueError:
                        pass
            
            logging.info(f"Найдено {len(existing_versions)} существующих версий в репозитории")
        except subprocess.SubprocessError as e:
            logging.error(f"Ошибка при получении истории коммитов: {e}")
    
    success = True
    processed_count = 0
    
    # Создаем коммиты для каждой папки с версией
    # Важно: сортируем по времени создания для сохранения хронологического порядка
    for folder in sorted(folders, key=lambda x: x["creation_time"]):
        version = folder["version"]
        
        # Проверяем, существует ли уже эта версия в репозитории
        if append_mode and version in existing_versions:
            logging.info(f"Пропуск версии {version}, так как она уже существует в репозитории")
            continue
        
        folder_path = folder["path"]
        creation_time = folder["creation_time"]
        folder_name = os.path.basename(folder_path)
        
        logging.info(f"Обработка папки: {folder_name} (версия: {version})")
        
        # Очищаем репозиторий от предыдущих файлов (кроме .git)
        if not clear_repository(target_dir):
            logging.error(f"Не удалось очистить репозиторий для версии {version}")
            success = False
            continue
        
        # Копируем файлы из папки версии в репозиторий
        file_count = copy_files(folder_path, target_dir)
        
        if file_count == 0:
            logging.warning(f"В папке {folder_name} не найдено файлов для добавления в репозиторий")
            continue
        
        # Создаем коммит с указанием автора и даты
        commit_success = create_commit(
            target_dir, 
            version, 
            folder_name, 
            creation_time, 
            file_count,
            author_name, 
            author_email, 
            msg_template
        )
        
        if commit_success:
            processed_count += 1
            logging.info(f"Создан коммит для версии {version} ({folder_name})")
        else:
            logging.error(f"Не удалось создать коммит для версии {version}")
            success = False
    
    logging.info(f"Обработка завершена. Успешно создано {processed_count} коммитов из {len(folders)} папок.")
    return success


def init_repo(repo_path):
    """
    Инициализирует Git-репозиторий
    
    :param repo_path: Путь к репозиторию
    :return: True если инициализация успешна, иначе False
    """
    try:
        logger.info(f"Инициализация Git-репозитория в {repo_path}")
        
        # Создаем директорию, если она не существует
        if not os.path.exists(repo_path):
            os.makedirs(repo_path)
            
        # Инициализируем Git-репозиторий
        result = subprocess.run(
            ['git', 'init'],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        if result.returncode != 0:
            logger.error(f"Ошибка при инициализации репозитория: {result.stderr}")
            return False
        
        logger.info(f"Репозиторий успешно инициализирован в {repo_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации репозитория: {str(e)}")
        return False


def clear_repo(repo_path):
    """
    Очищает репозиторий от всех файлов (кроме .git)
    
    :param repo_path: Путь к репозиторию
    :return: True если очистка успешна, иначе False
    """
    try:
        logger.info(f"Очистка репозитория {repo_path}")
        
        # Удаляем все файлы, кроме .git
        for item in os.listdir(repo_path):
            item_path = os.path.join(repo_path, item)
            if item != '.git':
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
        
        logger.info("Репозиторий успешно очищен")
        return True
    except Exception as e:
        logger.error(f"Ошибка при очистке репозитория: {str(e)}")
        return False


def add_files_to_git(files, repo_path):
    """
    Добавляет файлы в индекс Git
    
    :param files: Список файлов для добавления
    :param repo_path: Путь к репозиторию
    :return: True если добавление успешно, иначе False
    """
    try:
        logger.info(f"Добавление {len(files)} файлов в Git")
        
        # Добавляем все файлы в Git
        result = subprocess.run(
            ['git', 'add', '.'],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        if result.returncode != 0:
            logger.error(f"Ошибка при добавлении файлов в Git: {result.stderr}")
            return False
        
        logger.info("Файлы успешно добавлены в Git")
        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении файлов в Git: {str(e)}")
        return False


def find_versioned_folders(source_dir, pattern, extract_pattern, verbose=False):
    """Поиск папок с версиями проекта"""
    folders_info = []
    
    try:
        # Находим директории, соответствующие шаблону
        folder_pattern = os.path.join(source_dir, pattern)
        matching_folders = glob.glob(folder_pattern)
        
        # Проходим по найденным директориям
        for folder_path in matching_folders:
            if not os.path.isdir(folder_path):
                continue
                
            # Извлекаем имя папки без пути
            folder_name = os.path.basename(folder_path)
                
            # Извлекаем номер версии из имени папки
            version_str = extract_version_number(folder_name, extract_pattern)
            
            # Пробуем преобразовать версию в число (это может быть целое число или число с плавающей точкой)
            try:
                if '.' in version_str:
                    version = float(version_str)
                else:
                    version = int(version_str)
            except ValueError:
                version = version_str  # Оставляем как строку, если не удалось преобразовать
            
            # Получаем время создания папки на основе анализа файлов
            creation_time = get_folder_creation_time(folder_path)
            
            # Добавляем информацию о папке в список
            folder_info = {
                "path": folder_path,
                "name": folder_name,
                "version": version,
                "creation_time": creation_time
            }
            
            folders_info.append(folder_info)
            
            # Выводим информацию о найденной папке
            if verbose:
                print(f"{folder_name} (версия: {version})")
    
    except Exception as e:
        logging.error(f"Ошибка при поиске папок с версиями: {e}")
        import traceback
        logging.error(traceback.format_exc())
    
    # Сортировка папок по времени создания (для хронологического порядка)
    folders_info = sorted(folders_info, key=lambda x: x["creation_time"])
    
    logging.info(f"Найдено {len(folders_info)} папок с версиями:")
    for i, folder in enumerate(folders_info, 1):
        creation_date = datetime.fromtimestamp(folder["creation_time"]).strftime('%Y-%m-%d %H:%M:%S')
        logging.info(f"  {i}. {folder['name']} (версия: {folder['version']}, создан: {creation_date})")
    
    return folders_info


def run_git_command(command, repo_path):
    """Выполнение Git-команды в указанной директории"""
    try:
        result = subprocess.run(
            command,
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Ошибка при выполнении Git-команды: {e.cmd}")
        logging.error(f"Stderr: {e.stderr}")
        return False
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при выполнении Git-команды: {e}")
        return False


def clear_repository(repo_path):
    """Очистка репозитория от всех файлов, кроме директории .git"""
    try:
        # Получаем список всех файлов и директорий, кроме .git
        items = [os.path.join(repo_path, item) for item in os.listdir(repo_path) 
                if item != '.git' and not item.startswith('.git')]
        
        # Удаляем каждый файл/директорию
        for item in items:
            if os.path.isdir(item) and not os.path.islink(item):
                shutil.rmtree(item)
            else:
                os.remove(item)
        
        return True
    except Exception as e:
        logging.error(f"Ошибка при очистке репозитория: {e}")
        return False


def main():
    """Основная функция программы"""
    # Парсим аргументы командной строки
    args = parse_args()
    
    # Настраиваем уровень логирования
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    # Устанавливаем начальные значения
    source_dir = os.path.abspath(args.source_dir)
    pattern = args.pattern
    extract_pattern = args.extract_pattern
    target_dir = os.path.abspath(args.target_dir)
    dry_run = args.dry_run
    verbose = args.verbose
    author_file = args.authors_file
    msg_template = args.message_template
    author_name = args.author
    author_email = args.email
    append = args.append
    
    # Измеряем время выполнения
    start_time = time.time()
    
    logger.info(f"Запуск миграции из {source_dir}")
    logger.info(f"Шаблон извлечения версии: {extract_pattern}")
    
    # Находим папки с версиями
    folders_info = find_versioned_folders(source_dir, pattern, extract_pattern, verbose)
    
    # Проверяем наличие папок
    if not folders_info:
        logger.error("Не найдены папки с версиями проекта")
        sys.exit(1)
    
    # Вызываем миграцию папок в Git с учетом нового параметра
    if not dry_run:
        migrate_result = migrate_folders_to_git(
            source_dir, 
            target_dir, 
            folders_info, 
            dry_run,
            author_name,
            author_email,
            msg_template,
            append
        )
        if migrate_result:
            logging.info(f"Успешно создан Git-репозиторий в {target_dir}")
        else:
            logging.error("Произошли ошибки при создании репозитория")
    
    # Выводим время выполнения
    elapsed_time = time.time() - start_time
    logger.info(f"Успешно завершено за {elapsed_time:.2f} секунд")
    logger.info(f"Репозиторий создан в: {target_dir}")
    logger.info(f'Для просмотра истории выполните: cd "{target_dir}" && git log --oneline')


if __name__ == "__main__":
    sys.exit(main()) 