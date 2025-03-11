#!/bin/bash

# Скрипт для локальной сборки и тестирования приложения FolderToGit

set -e

echo "Начинаю сборку FolderToGit..."

# Определяем архитектуру
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
    GOARCH="arm64"
else
    GOARCH="amd64"
fi

echo "Архитектура: $GOARCH"

# Устанавливаем переменные окружения
export GOARCH=$GOARCH
export CGO_ENABLED=1

# Проверяем наличие зависимостей
if ! command -v go &> /dev/null; then
    echo "Go не установлен. Установите Go 1.21 или выше."
    exit 1
fi

if ! command -v fyne &> /dev/null; then
    echo "Fyne не установлен. Устанавливаю..."
    go install fyne.io/fyne/v2/cmd/fyne@latest
fi

# Загружаем зависимости
echo "Загружаю зависимости..."
go mod download

# Компилируем приложение
echo "Компилирую приложение..."
cd cmd/gui
go build -o FolderToGit

# Создаем .app пакет
echo "Создаю .app пакет..."
fyne package -os darwin -icon ../../Icon.png -name FolderToGit -executable FolderToGit -release

# Проверяем, что исполняемый файл существует и имеет правильное имя
if [ ! -f "FolderToGit.app/Contents/MacOS/FolderToGit" ]; then
    echo "Ошибка: Исполняемый файл не найден или имеет неправильное имя"
    ls -la FolderToGit.app/Contents/MacOS/
    exit 1
fi

# Копируем приложение в /Applications для тестирования
echo "Копирую приложение в /Applications для тестирования..."
sudo cp -R FolderToGit.app /Applications/

echo "Сборка завершена успешно!"
echo "Приложение установлено в /Applications/FolderToGit.app"
echo "Запустите приложение командой: open /Applications/FolderToGit.app"

# Запускаем приложение
open /Applications/FolderToGit.app 