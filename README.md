[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
![Python](https://shields.io/badge/python-3.10-blue)

# APA7 Bibliography Validator

A command-line tool to validate APA-7 formatted bibliography entries in a Word (DOCX) document. Supports translations via GNU gettext with default locale `zh_CN`.

## Features

* Validates six APA-7 reference types:
  * Thesis/Dissertation
  * Book Chapter
  * Edited Book
  * Journal Article
  * Conference Article
  * Monograph/Book

* Checks for:
  * Italics on titles, journal names, and volumes
  * Proper punctuation and ordering
  * Hanging indent and line spacing
  * Alphabetical ordering by author surname
* Rich error messages in the console (using Rich)
* Internationalization (i18n) with gettext; default messages in Chinese (`zh_CN`)

## Project Structure

```
├── locales/
│   ├── apa7_bib_validator.pot
│   └── zh_CN/
│       └── LC_MESSAGES/
│           ├── apa7_bib_validator.po
│           └── apa7_bib_validator.mo
├── i18n.py
├── apa7_bib_validator.py   # Main Script
└── sample/                 # Example `.docx` files for testing
```

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/apa7-bib-validator.git
   cd apa7-bib-validator
   ```

2. Create and activate a virtual environment:

   ```bash
    uv sync
   ```

## Command‑Line Arguments

The validator uses `argparse` to accept the document path and locale:

```python
parser.add_argument(
    '-d', '--docx_path',
    required=True,
    help="Path to the Word document to validate (e.g. references.docx)"
)
parser.add_argument(
    '-l', '--lang',
    default='zh_CN',
    help="Locale code for messages (default: zh_CN)"
)
```

## Usage

```bash
# Validate in Chinese (default)
python apa7_bib_validator.py -d sample/references.docx

# Validate in English
python apa7_bib_validator.py -d sample/references.docx -l en_US
```

## Internationalization

1. **Extract** all translatable strings into a POT file:

   ```bash
   xgettext --keyword=_ --language=Python -o apa7_bib_validator.pot *.py
   ```

2. **Merge** only new strings into your existing Chinese `.po`, using the `-u` (update) and `-v` (verbose) flags:

   ```bash
   msgmerge -uv \
     locales/zh_CN/LC_MESSAGES/apa7_bib_validator.po \
     apa7_bib_validator.pot
   ```

3. **Compile** the updated `.po` into a binary `.mo`:

   ```bash
   msgfmt -o locales/zh_CN/LC_MESSAGES/apa7_bib_validator.mo \
          locales/zh_CN/LC_MESSAGES/apa7_bib_validator.po
   ```

4. **Run** with the desired locale:

   ```bash
   python validate.py -d references.docx -l zh_CN
   ```

## License

Distributed under the MIT License. See `LICENSE` for details.
