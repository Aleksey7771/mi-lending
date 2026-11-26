# OCR Tool — Установка

## 1. Python-зависимости

```
pip install -r tools/ocr/requirements.txt
```

## 2. Tesseract OCR (для картинок и скриншотов)

> Если тебе нужны только PDF — этот шаг можно пропустить.

1. Скачай установщик: https://github.com/UB-Mannheim/tesseract/wiki  
   Файл: `tesseract-ocr-w64-setup-*.exe`

2. При установке отметь языковой пакет **Russian**.

3. Установи в папку по умолчанию:  
   `C:\Program Files\Tesseract-OCR\`

4. Проверь установку:
   ```
   tesseract --version
   ```

## 3. Использование

**Терминал:**
```
python tools/ocr/ocr.py путь/к/файлу.pdf
python tools/ocr/ocr.py путь/к/скриншоту.png
```
Текст появится в терминале и скопируется в буфер обмена.

**Claude Code (VSCode):**
```
/ocr путь/к/файлу.pdf
```

## Поддерживаемые форматы

- PDF: `.pdf`
- Картинки: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`
