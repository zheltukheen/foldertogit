package main

import (
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"os"
)

func main() {
	// Создаем новое изображение 1024x1024 (для Retina дисплеев)
	img := image.NewRGBA(image.Rect(0, 0, 1024, 1024))

	// Заполняем фон белым цветом
	draw.Draw(img, img.Bounds(), &image.Uniform{color.White}, image.Point{}, draw.Src)

	// Создаем синий круг
	center := image.Point{512, 512}
	radius := 400
	blue := color.RGBA{0, 122, 255, 255} // iOS-style blue

	for y := 0; y < 1024; y++ {
		for x := 0; x < 1024; x++ {
			dx := float64(x - center.X)
			dy := float64(y - center.Y)
			d := dx*dx + dy*dy
			if d < float64(radius*radius) {
				img.Set(x, y, blue)
			}
		}
	}

	// Создаем файл для сохранения
	f, _ := os.Create("Icon.png")
	defer f.Close()

	// Сохраняем изображение в PNG
	png.Encode(f, img)
}
