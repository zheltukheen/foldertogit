#!/usr/bin/env python3
"""
Folder to Git - Скрипт-обертка для запуска инструмента миграции папок в Git

Этот скрипт определяет, какую версию инструмента запустить (Python или Shell)
в зависимости от доступности и платформы.

Использование:
    python run.py --source /путь/к/папкам/с/версиями --target /путь/к/репозиторию [опции]

Все аргументы передаются выбранному скрипту.
"""

import os
import sys
import platform
import subprocess
import shutil


def find_script_path(file_name):
    """Определяет полный путь к скрипту в директории этого файла"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, file_name)


def is_executable(file_path):
    """Проверяет, является ли файл исполняемым"""
    return os.path.isfile(file_path) and os.access(file_path, os.X_OK)


def run_python_script():
    """Запускает Python-версию скрипта"""
    script_path = find_script_path("folder_to_git.py")
    
    if not os.path.exists(script_path):
        print(f"Ошибка: Не найден файл {script_path}")
        return 1
    
    python_cmd = sys.executable
    cmd = [python_cmd, script_path] + sys.argv[1:]
    
    return subprocess.call(cmd)


def run_shell_script():
    """Запускает Shell-версию скрипта"""
    script_path = find_script_path("folder_to_git.sh")
    
    if not os.path.exists(script_path):
        print(f"Ошибка: Не найден файл {script_path}")
        return 1
    
    # Делаем скрипт исполняемым, если он еще не является таковым
    if not is_executable(script_path):
        os.chmod(script_path, 0o755)
    
    # На Windows используем bash из Git for Windows, если он доступен
    if platform.system() == "Windows":
        # Ищем bash в стандартных местах установки Git for Windows
        git_bash_paths = [
            "C:/Program Files/Git/bin/bash.exe",
            "C:/Program Files (x86)/Git/bin/bash.exe",
            os.path.expanduser("~/AppData/Local/Programs/Git/bin/bash.exe")
        ]
        
        bash_path = None
        for path in git_bash_paths:
            if os.path.exists(path):
                bash_path = path
                break
        
        if bash_path:
            cmd = [bash_path, script_path] + sys.argv[1:]
        else:
            print("Ошибка: Не найден bash. Установите Git for Windows или используйте Python-версию.")
            return 1
    else:
        # На Unix-подобных системах
        cmd = [script_path] + sys.argv[1:]
    
    return subprocess.call(cmd)


def main():
    """Определяет, какой скрипт запустить"""
    # Если запущен без параметров или с параметром --help, показываем помощь
    if len(sys.argv) == 1 or "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        print("\nПопробуйте один из следующих вариантов:")
        print("  python run.py --help  # для получения полной справки")
        print("  python folder_to_git.py --help  # для Python-версии")
        print("  ./folder_to_git.sh --help  # для Shell-версии")
        return 0
    
    # Приоритет: 1) Python-скрипт 2) Shell-скрипт
    py_script = find_script_path("folder_to_git.py")
    sh_script = find_script_path("folder_to_git.sh")
    
    if os.path.exists(py_script):
        return run_python_script()
    elif os.path.exists(sh_script):
        return run_shell_script()
    else:
        print("Ошибка: Не найдены скрипты folder_to_git.py или folder_to_git.sh")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 