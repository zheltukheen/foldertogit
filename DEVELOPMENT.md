# Руководство для разработчиков FolderToGit

Этот документ содержит инструкции для разработчиков по сборке, тестированию и выпуску новых версий приложения FolderToGit.

## Структура проекта

```
foldertogit/
├── cmd/
│   ├── gui/           # Основной код GUI-приложения
│   │   ├── main.go    # Точка входа в приложение
│   │   └── Info.plist # Метаданные для macOS
│   └── icon/          # Ресурсы для иконок
├── pkg/
│   └── gitconverter/  # Основная логика конвертации
│       └── converter.go
├── .github/
│   └── workflows/     # Конфигурация GitHub Actions
│       └── build.yml  # Автоматическая сборка релизов
├── FyneApp.toml       # Конфигурация Fyne
├── go.mod             # Зависимости Go
├── go.sum             # Хеши зависимостей
└── build_local.sh     # Скрипт для локальной сборки
```

## Требования для разработки

- Go 1.21 или выше
- [Fyne](https://fyne.io/) toolkit
- Git
- Для macOS: Xcode Command Line Tools
- Для Windows: MinGW или MSYS2

## Локальная сборка

### macOS

Для сборки и тестирования приложения на macOS используйте скрипт `build_local.sh`:

```bash
./build_local.sh
```

Скрипт автоматически:
1. Определит архитектуру вашего компьютера (arm64 или amd64)
2. Установит необходимые зависимости
3. Скомпилирует приложение
4. Создаст .app пакет
5. Установит приложение в директорию /Applications
6. Запустит приложение для тестирования

### Windows

Для сборки на Windows:

```bash
cd cmd/gui
go build -ldflags="-H windowsgui" -o FolderToGit.exe
```

## Выпуск новой версии

1. Обновите версию в следующих файлах:
   - `cmd/gui/Info.plist` (CFBundleVersion и CFBundleShortVersionString)
   - `FyneApp.toml` (Version и Build)

2. Протестируйте приложение локально с помощью скрипта `build_local.sh`

3. Создайте тег с новой версией и отправьте его в репозиторий:
   ```bash
   git tag v1.0.x
   git push origin v1.0.x
   ```

4. GitHub Actions автоматически соберет релизы для Windows и macOS и опубликует их на странице релизов.

## Устранение проблем

### Проблемы с именем исполняемого файла

Убедитесь, что имя исполняемого файла в `Info.plist` (CFBundleExecutable) соответствует имени, указанному при сборке.

### Проблемы с установкой на macOS

Если приложение не устанавливается или не запускается на macOS:
1. Проверьте структуру .app пакета: `ls -la /Applications/FolderToGit.app/Contents/MacOS/`
2. Убедитесь, что исполняемый файл имеет правильное имя и права доступа
3. Проверьте наличие карантина: `xattr -l /Applications/FolderToGit.app`
4. При необходимости снимите карантин: `xattr -d com.apple.quarantine /Applications/FolderToGit.app`

### Проблемы с подписью

Для распространения приложения через App Store или для избежания предупреждений безопасности, подпишите приложение с помощью сертификата разработчика:

```bash
codesign --force --deep --sign "Developer ID Application: Your Name" /Applications/FolderToGit.app
``` 