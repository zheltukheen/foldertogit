package main

import (
	"fmt"
	"image/color"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/theme"
	"fyne.io/fyne/v2/widget"
	"github.com/ncruces/zenity"

	"folder_to_git/pkg/gitconverter"
)

type GUI struct {
	window fyne.Window
	config gitconverter.Config

	// Виджеты
	sourceEntry   *widget.Entry
	targetEntry   *widget.Entry
	patternEntry  *widget.Entry
	extractEntry  *widget.Entry
	authorEntry   *widget.Entry
	emailEntry    *widget.Entry
	dryRunCheck   *widget.Check
	verboseCheck  *widget.Check
	appendCheck   *widget.Check
	logText       *widget.TextGrid
	convertButton *widget.Button
}

func main() {
	a := app.NewWithID("com.foldertogit.app")
	a.Settings().SetTheme(newNativeTheme())
	window := a.NewWindow("Конвертер папок в Git")

	gui := &GUI{
		window: window,
		config: gitconverter.Config{
			Pattern:        "*",
			ExtractPattern: "[0-9]+(\\.[0-9]+)?",
			Author:         "Developer",
			Email:          "dev@example.com",
		},
	}

	gui.setupUI()
	window.Resize(fyne.NewSize(700, 750))
	window.ShowAndRun()
}

func (g *GUI) setupUI() {
	// Создаем элементы ввода с нативным стилем
	g.sourceEntry = widget.NewEntry()
	g.sourceEntry.SetPlaceHolder("./versions или /путь/к/папкам/с/версиями")
	g.sourceEntry.Resize(fyne.NewSize(300, g.sourceEntry.MinSize().Height))
	styleNativeEntry(g.sourceEntry)

	g.targetEntry = widget.NewEntry()
	g.targetEntry.SetPlaceHolder("./git_repo или /путь/к/репозиторию")
	g.targetEntry.Resize(fyne.NewSize(300, g.targetEntry.MinSize().Height))
	styleNativeEntry(g.targetEntry)

	g.patternEntry = widget.NewEntry()
	g.patternEntry.SetText(g.config.Pattern)
	g.patternEntry.SetPlaceHolder("version_* или project_v*")
	g.patternEntry.Resize(fyne.NewSize(300, g.patternEntry.MinSize().Height))
	styleNativeEntry(g.patternEntry)

	g.extractEntry = widget.NewEntry()
	g.extractEntry.SetText(g.config.ExtractPattern)
	g.extractEntry.SetPlaceHolder("[0-9]+ или v([0-9]+)")
	g.extractEntry.Resize(fyne.NewSize(300, g.extractEntry.MinSize().Height))
	styleNativeEntry(g.extractEntry)

	g.authorEntry = widget.NewEntry()
	g.authorEntry.SetText(g.config.Author)
	g.authorEntry.SetPlaceHolder("Иван Иванов")
	g.authorEntry.Resize(fyne.NewSize(300, g.authorEntry.MinSize().Height))
	styleNativeEntry(g.authorEntry)

	g.emailEntry = widget.NewEntry()
	g.emailEntry.SetText(g.config.Email)
	g.emailEntry.SetPlaceHolder("ivan@example.com")
	g.emailEntry.Resize(fyne.NewSize(300, g.emailEntry.MinSize().Height))
	styleNativeEntry(g.emailEntry)

	// Кнопки выбора директорий с нативным стилем
	sourceBrowse := widget.NewButtonWithIcon("Обзор", theme.FolderOpenIcon(), func() {
		path, err := zenity.SelectFile(
			zenity.Title("Выберите исходную директорию"),
			zenity.Directory(),
		)
		if err == nil && path != "" {
			g.sourceEntry.SetText(path)
		}
	})
	styleNativeButton(sourceBrowse)

	targetBrowse := widget.NewButtonWithIcon("Обзор", theme.FolderOpenIcon(), func() {
		path, err := zenity.SelectFile(
			zenity.Title("Выберите целевую директорию"),
			zenity.Directory(),
		)
		if err == nil && path != "" {
			g.targetEntry.SetText(path)
		}
	})
	styleNativeButton(targetBrowse)

	// Чекбоксы
	g.dryRunCheck = widget.NewCheck("Тестовый режим", nil)
	g.verboseCheck = widget.NewCheck("Подробный вывод", nil)
	g.appendCheck = widget.NewCheck("Добавить к существующему", nil)

	// Лог
	g.logText = widget.NewTextGrid()
	g.logText.SetText("Добро пожаловать в Folder to Git Converter!\nЗаполните необходимые поля и нажмите 'Начать конвертацию'")

	// Кнопка конвертации с нативным стилем
	g.convertButton = widget.NewButtonWithIcon("Начать конвертацию", theme.MediaPlayIcon(), g.startConversion)
	styleNativePrimaryButton(g.convertButton)

	// Компоновка интерфейса
	form := &widget.Form{
		Items: []*widget.FormItem{
			{Text: "Исходная директория", Widget: container.NewBorder(nil, nil, nil, sourceBrowse, g.sourceEntry)},
			{Text: "Целевой репозиторий", Widget: container.NewBorder(nil, nil, nil, targetBrowse, g.targetEntry)},
			{Text: "Шаблон поиска", Widget: g.patternEntry},
			{Text: "Шаблон версии", Widget: g.extractEntry},
			{Text: "Имя автора", Widget: g.authorEntry},
			{Text: "Email автора", Widget: g.emailEntry},
		},
	}

	options := container.NewHBox(
		g.dryRunCheck,
		g.verboseCheck,
		g.appendCheck,
	)

	buttons := container.NewHBox(
		g.convertButton,
		widget.NewButtonWithIcon("Очистить лог", theme.ContentClearIcon(), func() {
			g.logText.SetText("")
		}),
	)

	// Создаем заголовки
	optionsLabel := widget.NewLabel("Дополнительные опции")
	optionsLabel.TextStyle = fyne.TextStyle{Bold: true}
	logLabel := widget.NewLabel("Лог операций")
	logLabel.TextStyle = fyne.TextStyle{Bold: true}

	// Создаем скроллируемый контейнер для лога с фиксированной высотой
	logScroll := container.NewScroll(g.logText)
	logScroll.SetMinSize(fyne.NewSize(500, 200))

	// Основной контейнер с вертикальной прокруткой
	mainContainer := container.NewVBox(
		form,
		container.NewVBox(
			optionsLabel,
			widget.NewCard("", "", options),
		),
		buttons,
		container.NewVBox(
			logLabel,
			widget.NewCard("", "", logScroll),
		),
	)

	// Оборачиваем основной контейнер в вертикальный скролл
	scrollContainer := container.NewVScroll(mainContainer)

	// Добавляем отступы и устанавливаем контент
	content := container.NewPadded(scrollContainer)
	g.window.SetContent(content)
}

// Добавляем вспомогательные функции для стилизации
func styleNativeEntry(entry *widget.Entry) {
	entry.TextStyle = fyne.TextStyle{
		Bold:      false,
		Italic:    false,
		Monospace: false,
	}
}

func styleNativeButton(button *widget.Button) {
	button.Importance = widget.MediumImportance
}

func styleNativePrimaryButton(button *widget.Button) {
	button.Importance = widget.HighImportance
}

// Создаем кастомную тему для нативного вида
type nativeTheme struct {
	defaultTheme fyne.Theme
}

func newNativeTheme() *nativeTheme {
	return &nativeTheme{
		defaultTheme: theme.DefaultTheme(),
	}
}

func (t *nativeTheme) Font(s fyne.TextStyle) fyne.Resource {
	if s.Monospace {
		return t.defaultTheme.Font(s)
	}
	return t.defaultTheme.Font(s)
}

func (t *nativeTheme) Color(n fyne.ThemeColorName, v fyne.ThemeVariant) color.Color {
	switch n {
	case theme.ColorNameBackground:
		return color.NRGBA{R: 236, G: 236, B: 236, A: 255}
	case theme.ColorNameButton:
		return color.NRGBA{R: 224, G: 224, B: 224, A: 255}
	case theme.ColorNameDisabled:
		return color.NRGBA{R: 150, G: 150, B: 150, A: 255}
	case theme.ColorNameForeground:
		return color.NRGBA{R: 0, G: 0, B: 0, A: 255}
	case theme.ColorNamePrimary:
		return color.NRGBA{R: 0, G: 122, B: 255, A: 255}
	default:
		return t.defaultTheme.Color(n, v)
	}
}

func (t *nativeTheme) Icon(n fyne.ThemeIconName) fyne.Resource {
	return t.defaultTheme.Icon(n)
}

func (t *nativeTheme) Size(s fyne.ThemeSizeName) float32 {
	switch s {
	case theme.SizeNamePadding:
		return 8
	case theme.SizeNameInlineIcon:
		return 20
	case theme.SizeNameScrollBar:
		return 12
	case theme.SizeNameScrollBarSmall:
		return 3
	case theme.SizeNameText:
		return 14
	case theme.SizeNameInputBorder:
		return 1
	default:
		return t.defaultTheme.Size(s)
	}
}

func (g *GUI) startConversion() {
	// Проверяем входные данные
	if g.sourceEntry.Text == "" {
		dialog.ShowError(fmt.Errorf("укажите исходную директорию"), g.window)
		return
	}
	if g.targetEntry.Text == "" {
		dialog.ShowError(fmt.Errorf("укажите целевую директорию"), g.window)
		return
	}

	// Обновляем конфигурацию
	g.config.SourceDir = g.sourceEntry.Text
	g.config.TargetDir = g.targetEntry.Text
	g.config.Pattern = g.patternEntry.Text
	g.config.ExtractPattern = g.extractEntry.Text
	g.config.Author = g.authorEntry.Text
	g.config.Email = g.emailEntry.Text
	g.config.DryRun = g.dryRunCheck.Checked
	g.config.Verbose = g.verboseCheck.Checked
	g.config.Append = g.appendCheck.Checked

	// Отключаем кнопку на время конвертации
	g.convertButton.Disable()
	g.convertButton.SetText("Выполняется...")

	// Запускаем конвертацию в отдельной горутине
	go func() {
		defer func() {
			g.convertButton.Enable()
			g.convertButton.SetText("Начать конвертацию")
		}()

		// Ищем папки с версиями
		g.log("Начинаем поиск папок с версиями...")
		folders, err := gitconverter.FindVersionedFolders(g.config)
		if err != nil {
			g.logError("Ошибка поиска папок:", err)
			return
		}

		if len(folders) == 0 {
			g.logError("Не найдены папки с версиями", nil)
			return
		}

		g.log(fmt.Sprintf("Найдено %d папок с версиями", len(folders)))

		// Выполняем миграцию
		if err := gitconverter.MigrateToGit(g.config, folders); err != nil {
			g.logError("Ошибка миграции:", err)
			return
		}

		if !g.config.DryRun {
			g.logSuccess(fmt.Sprintf("Git-репозиторий успешно создан в: %s", g.config.TargetDir))
		} else {
			g.log("Тестовый режим завершен")
		}
	}()
}

func (g *GUI) log(msg string) {
	g.logText.SetText(g.logText.Text() + "\n" + msg)
}

func (g *GUI) logError(msg string, err error) {
	if err != nil {
		msg = fmt.Sprintf("%s %v", msg, err)
	}
	dialog.ShowError(fmt.Errorf(msg), g.window)
	g.log("ОШИБКА: " + msg)
}

func (g *GUI) logSuccess(msg string) {
	dialog.ShowInformation("Успех", msg, g.window)
	g.log("УСПЕХ: " + msg)
}
