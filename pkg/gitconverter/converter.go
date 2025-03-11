package gitconverter

import (
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/plumbing"
	"github.com/go-git/go-git/v5/plumbing/object"
)

// FolderInfo содержит информацию о папке с версией
type FolderInfo struct {
	Path         string
	Version      string
	CreationTime int64 // Unix timestamp времени создания
}

// Config содержит настройки для конвертации
type Config struct {
	SourceDir       string
	TargetDir       string
	Pattern         string
	ExtractPattern  string
	DryRun          bool
	Author          string
	Email           string
	Verbose         bool
	Append          bool
	AuthorsFile     string // Файл с сопоставлением версий и авторов
	MessageTemplate string // Шаблон сообщения коммита
}

// FindVersionedFolders ищет папки с версиями проекта
func FindVersionedFolders(config Config) ([]FolderInfo, error) {
	var folders []FolderInfo

	// Создаем полный путь для поиска
	searchPattern := filepath.Join(config.SourceDir, config.Pattern)

	// Компилируем регулярное выражение для извлечения версии
	re, err := regexp.Compile(config.ExtractPattern)
	if err != nil {
		return nil, fmt.Errorf("ошибка в регулярном выражении: %v", err)
	}

	// Ищем папки, соответствующие шаблону
	matches, err := filepath.Glob(searchPattern)
	if err != nil {
		return nil, fmt.Errorf("ошибка при поиске папок: %v", err)
	}

	// Обрабатываем каждую найденную папку
	for _, path := range matches {
		// Проверяем, что это директория
		info, err := os.Stat(path)
		if err != nil || !info.IsDir() {
			continue
		}

		// Получаем имя папки
		name := filepath.Base(path)

		// Извлекаем версию из имени папки
		version := ""
		if match := re.FindString(name); match != "" {
			version = match
		} else {
			if config.Verbose {
				log.Printf("Не удалось извлечь версию из папки: %s", name)
			}
			continue
		}

		// Получаем время создания папки
		creationTime := getFolderCreationTime(path)

		folders = append(folders, FolderInfo{
			Path:         path,
			Version:      version,
			CreationTime: creationTime,
		})

		if config.Verbose {
			log.Printf("Найдена папка: %s (версия: %s, создана: %s)",
				name, version, time.Unix(creationTime, 0).Format("2006-01-02 15:04:05"))
		}
	}

	// Сортируем папки по времени создания
	sort.Slice(folders, func(i, j int) bool {
		return folders[i].CreationTime < folders[j].CreationTime
	})

	if len(folders) == 0 {
		return nil, fmt.Errorf("не найдены папки с версиями в %s", config.SourceDir)
	}

	log.Printf("Найдено %d папок с версиями:", len(folders))
	for i, folder := range folders {
		log.Printf("  %d. %s (версия: %s, создана: %s)",
			i+1,
			filepath.Base(folder.Path),
			folder.Version,
			time.Unix(folder.CreationTime, 0).Format("2006-01-02 15:04:05"))
	}

	return folders, nil
}

// MigrateToGit выполняет миграцию папок в Git-репозиторий
func MigrateToGit(config Config, folders []FolderInfo) error {
	if config.DryRun {
		log.Println("Запущен тестовый режим (dry-run), Git-репозиторий не будет создан")
		return nil
	}

	// Создаем директорию для репозитория, если её нет
	if err := os.MkdirAll(config.TargetDir, 0755); err != nil {
		return fmt.Errorf("ошибка создания директории: %v", err)
	}

	// Проверяем существование репозитория
	gitDir := filepath.Join(config.TargetDir, ".git")
	repoExists := false
	if _, err := os.Stat(gitDir); err == nil {
		repoExists = true
	}

	var repo *git.Repository
	var err error

	// Инициализируем или открываем репозиторий
	if !repoExists && !config.Append {
		repo, err = git.PlainInit(config.TargetDir, false)
		if err != nil {
			return fmt.Errorf("ошибка инициализации репозитория: %v", err)
		}
		log.Printf("Инициализирован новый репозиторий в %s", config.TargetDir)
	} else if config.Append && !repoExists {
		return fmt.Errorf("указан режим --append, но репозиторий не существует в %s", config.TargetDir)
	} else {
		repo, err = git.PlainOpen(config.TargetDir)
		if err != nil {
			return fmt.Errorf("ошибка открытия репозитория: %v", err)
		}
		log.Printf("Открыт существующий репозиторий в %s", config.TargetDir)
	}

	// Получаем существующие версии, если используется режим добавления
	existingVersions := make(map[string]bool)
	if config.Append {
		refs, err := repo.References()
		if err != nil {
			return fmt.Errorf("ошибка получения ссылок: %v", err)
		}
		err = refs.ForEach(func(ref *plumbing.Reference) error {
			if ref.Type() == plumbing.HashReference {
				commit, err := repo.CommitObject(ref.Hash())
				if err != nil {
					return nil
				}
				// Извлекаем версию из сообщения коммита
				if strings.Contains(commit.Message, "Version") {
					parts := strings.Split(commit.Message, ":")
					if len(parts) > 0 {
						version := strings.TrimSpace(strings.TrimPrefix(parts[0], "Version"))
						existingVersions[version] = true
					}
				}
			}
			return nil
		})
		if err != nil {
			return fmt.Errorf("ошибка при анализе истории: %v", err)
		}
	}

	worktree, err := repo.Worktree()
	if err != nil {
		return fmt.Errorf("ошибка получения рабочей директории: %v", err)
	}

	// Обрабатываем каждую папку
	for _, folder := range folders {
		// Пропускаем существующие версии в режиме добавления
		if config.Append && existingVersions[folder.Version] {
			log.Printf("Пропуск версии %s, так как она уже существует в репозитории", folder.Version)
			continue
		}

		log.Printf("Обработка папки: %s (версия: %s)", filepath.Base(folder.Path), folder.Version)

		// Очищаем рабочую директорию только если не в режиме добавления (append)
		if !config.Append {
			if err := clearDirectory(config.TargetDir); err != nil {
				return fmt.Errorf("ошибка очистки директории: %v", err)
			}
		}

		// Копируем файлы и получаем список новых файлов
		fileCount, newFiles, err := copyFilesAndTrack(folder.Path, config.TargetDir, config.Append)
		if err != nil {
			return fmt.Errorf("ошибка копирования файлов: %v", err)
		}

		if fileCount == 0 {
			log.Printf("В папке %s не найдено файлов для добавления", filepath.Base(folder.Path))
			continue
		}

		// Получаем информацию об авторе из файла, если он указан
		authorName := config.Author
		authorEmail := config.Email
		if config.AuthorsFile != "" {
			if name, email, err := getAuthorInfo(folder.Version, config.AuthorsFile); err == nil && name != "" && email != "" {
				authorName = name
				authorEmail = email
			}
		}

		// Формируем сообщение коммита
		var commitMsg string
		if config.MessageTemplate != "" {
			commitMsg = strings.ReplaceAll(config.MessageTemplate, "{version}", folder.Version)
			commitMsg = strings.ReplaceAll(commitMsg, "{folder}", filepath.Base(folder.Path))
			commitMsg = strings.ReplaceAll(commitMsg, "{date}", time.Unix(folder.CreationTime, 0).Format("2006-01-02 15:04:05"))
			commitMsg = strings.ReplaceAll(commitMsg, "{files}", fmt.Sprintf("%d", fileCount))
			commitMsg = strings.ReplaceAll(commitMsg, "{author}", authorName)
		} else {
			commitMsg = fmt.Sprintf("Version %s: %s (created: %s)",
				folder.Version,
				filepath.Base(folder.Path),
				time.Unix(folder.CreationTime, 0).Format("2006-01-02 15:04:05"))
		}

		// Добавляем только новые файлы в индекс
		for _, file := range newFiles {
			relPath, err := filepath.Rel(config.TargetDir, file)
			if err != nil {
				log.Printf("Предупреждение: не удалось получить относительный путь для %s: %v", file, err)
				continue
			}
			_, err = worktree.Add(relPath)
			if err != nil {
				log.Printf("Предупреждение: не удалось добавить файл %s: %v", relPath, err)
			}
		}

		// Создаем коммит
		commit, err := worktree.Commit(commitMsg, &git.CommitOptions{
			Author: &object.Signature{
				Name:  authorName,
				Email: authorEmail,
				When:  time.Unix(folder.CreationTime, 0),
			},
		})

		if err != nil {
			return fmt.Errorf("ошибка создания коммита: %v", err)
		}

		log.Printf("Создан коммит %s для версии %s", commit.String(), folder.Version)
	}

	return nil
}

// clearDirectory удаляет все файлы и папки в указанной директории, кроме .git и системных директорий
func clearDirectory(dir string) error {
	// Список системных директорий и файлов, которые нужно игнорировать
	systemDirs := map[string]bool{
		".git":         true,
		".Trash":       true,
		".Trashes":     true,
		".config":      true,
		".cache":       true,
		".local":       true,
		"Library":      true,
		"Applications": true,
		"System":       true,
		"Users":        true,
		"bin":          true,
		"etc":          true,
		"usr":          true,
		"var":          true,
		"tmp":          true,
		"opt":          true,
	}

	// Проверяем, не является ли директория системной
	baseName := filepath.Base(dir)
	if systemDirs[baseName] {
		return nil // Пропускаем системные директории
	}

	// Проверяем, не находится ли директория в домашней директории пользователя
	homeDir, err := os.UserHomeDir()
	if err == nil {
		// Если директория находится в домашней директории и начинается с точки (скрытая),
		// то пропускаем её
		if strings.HasPrefix(dir, homeDir) {
			relPath, err := filepath.Rel(homeDir, dir)
			if err == nil && strings.HasPrefix(relPath, ".") && !strings.Contains(relPath, "..") {
				return nil
			}
		}
	}

	entries, err := os.ReadDir(dir)
	if err != nil {
		return err
	}

	for _, entry := range entries {
		// Игнорируем системные директории и файлы
		if systemDirs[entry.Name()] {
			continue
		}

		path := filepath.Join(dir, entry.Name())

		// Проверяем, не является ли файл символической ссылкой
		fileInfo, err := os.Lstat(path)
		if err != nil {
			return fmt.Errorf("не удалось получить информацию о файле %s: %v", path, err)
		}

		// Пропускаем символические ссылки
		if fileInfo.Mode()&os.ModeSymlink != 0 {
			continue
		}

		// Используем более безопасный подход к удалению файлов
		if entry.IsDir() {
			// Для директорий сначала рекурсивно удаляем содержимое
			if err := clearDirectory(path); err != nil {
				// Если не удалось очистить поддиректорию, просто логируем ошибку и продолжаем
				log.Printf("Предупреждение: %v", err)
				continue
			}
			// Затем удаляем саму директорию
			if err := os.Remove(path); err != nil {
				// Если не удалось удалить директорию, просто логируем ошибку и продолжаем
				log.Printf("Предупреждение: не удалось удалить директорию %s: %v", path, err)
				continue
			}
		} else {
			// Для файлов просто удаляем
			if err := os.Remove(path); err != nil {
				// Если не удалось удалить файл, просто логируем ошибку и продолжаем
				log.Printf("Предупреждение: не удалось удалить файл %s: %v", path, err)
				continue
			}
		}
	}
	return nil
}

// copyFilesAndTrack копирует файлы из исходной директории в целевую и возвращает список новых файлов
func copyFilesAndTrack(src, dst string, appendMode bool) (int, []string, error) {
	fileCount := 0
	var newFiles []string
	ignoreDirs := []string{".git", "__pycache__", "venv", ".venv", "node_modules", ".idea", ".vscode", "dist", "build", "env"}
	ignoreFiles := []string{".DS_Store", "*.pyc", "*.pyo", "*.pyd", ".gitignore", ".gitattributes", "*.swp", "*.swo", "*.log", "*.bak"}

	err := filepath.Walk(src, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		// Получаем относительный путь
		relPath, err := filepath.Rel(src, path)
		if err != nil {
			return err
		}

		// Пропускаем корневую директорию
		if relPath == "." {
			return nil
		}

		// Проверяем, нужно ли игнорировать директорию
		if info.IsDir() {
			for _, ignoreDir := range ignoreDirs {
				if info.Name() == ignoreDir {
					return filepath.SkipDir
				}
			}
			return nil
		}

		// Проверяем, нужно ли игнорировать файл
		for _, pattern := range ignoreFiles {
			matched, err := filepath.Match(pattern, info.Name())
			if err != nil {
				return err
			}
			if matched {
				return nil
			}
		}

		// Создаем директории в целевом пути
		targetPath := filepath.Join(dst, relPath)
		targetDir := filepath.Dir(targetPath)
		if err := os.MkdirAll(targetDir, 0755); err != nil {
			return err
		}

		// В режиме добавления проверяем, существует ли файл
		if appendMode {
			if _, err := os.Stat(targetPath); err == nil {
				// Файл уже существует, пропускаем его
				return nil
			}
		}

		// Копируем файл
		if err := copyFile(path, targetPath); err != nil {
			return err
		}

		// Добавляем путь к новому файлу в список
		newFiles = append(newFiles, targetPath)
		fileCount++
		return nil
	})

	return fileCount, newFiles, err
}

// copyFiles копирует файлы из исходной директории в целевую (для обратной совместимости)
func copyFiles(src, dst string, appendMode bool) (int, error) {
	count, _, err := copyFilesAndTrack(src, dst, appendMode)
	return count, err
}

// copyFile копирует один файл
func copyFile(src, dst string) error {
	sourceFile, err := os.Open(src)
	if err != nil {
		return err
	}
	defer sourceFile.Close()

	destFile, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer destFile.Close()

	if _, err := io.Copy(destFile, sourceFile); err != nil {
		return err
	}

	sourceInfo, err := os.Stat(src)
	if err != nil {
		return err
	}

	return os.Chmod(dst, sourceInfo.Mode())
}

// getAuthorInfo получает информацию об авторе из файла сопоставления
func getAuthorInfo(version string, authorsFile string) (string, string, error) {
	if authorsFile == "" {
		return "", "", nil
	}

	data, err := os.ReadFile(authorsFile)
	if err != nil {
		return "", "", err
	}

	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}

		parts := strings.Split(line, ":")
		if len(parts) >= 3 && parts[0] == version {
			return parts[1], parts[2], nil
		}
	}

	return "", "", nil
}

// getFolderCreationTime получает время создания папки на основе анализа файлов
func getFolderCreationTime(folderPath string) int64 {
	var fileTimes []int64
	keyFilePatterns := []string{
		"version.py", "version.txt", "VERSION",
		"main.py", "app.py", "bot.py", "config.py",
		"requirements.txt", "setup.py",
		"Dockerfile", "docker-compose.yml",
	}

	processedFiles := 0
	maxFiles := 500

	err := filepath.Walk(folderPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}

		// Пропускаем служебные директории
		if info.IsDir() {
			base := filepath.Base(path)
			if strings.HasPrefix(base, ".") || base == "__pycache__" ||
				base == "venv" || base == "env" || base == ".venv" {
				return filepath.SkipDir
			}
			return nil
		}

		if processedFiles >= maxFiles {
			return filepath.SkipDir
		}

		// Пропускаем служебные файлы
		base := filepath.Base(path)
		if strings.HasPrefix(base, ".") || strings.HasSuffix(base, ".pyc") {
			return nil
		}

		modTime := info.ModTime().Unix()
		fileTimes = append(fileTimes, modTime)

		// Проверяем, является ли файл ключевым
		for _, pattern := range keyFilePatterns {
			if strings.Contains(strings.ToLower(base), strings.ToLower(pattern)) {
				fileTimes = append(fileTimes, modTime)
				break
			}
		}

		processedFiles++
		return nil
	})

	if err != nil || len(fileTimes) == 0 {
		// Если не удалось получить времена файлов, возвращаем текущее время
		return time.Now().Unix()
	}

	// Сортируем времена и берем медиану
	sort.Slice(fileTimes, func(i, j int) bool {
		return fileTimes[i] < fileTimes[j]
	})

	return fileTimes[len(fileTimes)/2]
}
