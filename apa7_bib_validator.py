#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# apa7_bib_validator.py: APA7 bibliography validator
# Copyright (C) 2025 Henrique Lin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import argparse
import gettext
import re
from abc import ABC, abstractmethod

from docx import Document
from docx.oxml.ns import qn
from rich.console import Console
from rich.text import Text

_ = gettext.gettext

HINT_TEMPLATES = {
    "Thesis/Dissertation": lambda: Text.assemble(
        ("Example: ",),
        ("Doe, J.",),
        (" (2018). ",),
        ("The Effects of X on Y", "italic"),
        (" [Doctoral dissertation, University of Example].",)
    ),
    "Book Chapter": lambda: Text.assemble(
        ("Example: ",),
        ("Smith, A. B.",),
        (" (2019). Chapter Title. In C. D. Editor & E. F. Editor (Eds.), "),
        ("Book Title", "italic"),
        (" (pp. 12–34). Publisher.",)
    ),
    "Edited Book": lambda: Text.assemble(
        ("Example: ",),
        ("Jones, R.",),
        (" (Ed.). (2020). ",),
        ("Edited Book Title", "italic"),
        (". Publisher.",)
    ),
    "Journal Article": lambda: Text.assemble(
        ("Example: ",),
        ("Smith, J. A., & Doe, J. B.",),
        (" (2020). Understanding AI. ",),
        ("Journal of Research", "italic"),
        (", ",),
        ("15", "italic"),
        ("(3), 123–145.",)
    ),
    "Conference Article": lambda: Text.assemble(
        ("Example: ",),
        ("Lee, S.",),
        (" (2021). ",),
        ("Conference Paper Title", "italic"),
        (". Conference on Examples, City.",)
    ),
    "Monograph/Book": lambda: Text.assemble(
        ("Example: ",),
        ("Brown, C.",),
        (" (2017). ",),
        ("Fundamentals of Example Studies", "italic"),
        (". Publisher Name.",)
    ),
}

console = Console()

# --- Utility functions for formatting checks -----------------------------

def run_is_italic(run):
    """Return True if this run is italicized (directly or via XML)."""
    if run.italic or run.font.italic:
        return True
    rPr = run._element.rPr
    if rPr is not None:
        if rPr.find(qn('w:i')) is not None or rPr.find(qn('w:iCs')) is not None:
            return True
    return False

def is_snippet_italic(para, snippet):
    """Return True if the exact snippet in this paragraph is entirely italicized."""
    runs = para.runs
    full_text = "".join(run.text for run in runs)
    start = full_text.find(snippet)
    if start < 0:
        return False
    end = start + len(snippet)
    pos = 0
    for run in runs:
        run_len = len(run.text)
        run_start, run_end = pos, pos + run_len
        if run_end > start and run_start < end:
            if not run_is_italic(run):
                return False
        pos = run_end
    return True

def get_effective_font(style):
    """Traverse style inheritance to find font name and size."""
    name = style.font.name
    size = style.font.size
    if name and size:
        return name, size.pt
    base = getattr(style, 'base_style', None)
    if base:
        return get_effective_font(base)
    return None, None

def is_section_title(para, font_name='Times New Roman', font_size_pt=14):
    """Detect if a paragraph is a section title."""
    style_name = para.style.name.lower() if para.style and para.style.name else ''
    if 'heading' in style_name:
        return True
    eff_name, eff_size = (None, None)
    if para.style:
        eff_name, eff_size = get_effective_font(para.style)
    for run in para.runs:
        font = run.font
        name = font.name or eff_name
        size = font.size.pt if font.size else eff_size
        if font.bold and name == font_name and size == font_size_pt:
            return True
    return False

def get_bibliography_paragraphs(doc: Document):
    """
    Extract all non-empty paragraphs under the 'Bibliography' heading.
    Stops at the next section title or a blank-page marker.
    """
    in_bib = False
    entries = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not in_bib:
            if text.lower() == 'bibliography':
                in_bib = True
            continue
        if text == '[This page is deliberately left blank.]':
            break
        if text:
            entries.append((para, text))
    return entries

# --- Abstract base class for APA citation types -------------------------

class CitationType(ABC):
    name: str
    detect_re: re.Pattern

    @classmethod
    def detect(cls, text: str) -> bool:
        return bool(cls.detect_re.search(text))

    @abstractmethod
    def validate(self, text: str, para, cite: dict) -> None:
        """Append any errors for this citation to cite['errors']."""


# --- Six concrete citation-type validators -------------------------------

class ThesisCitation(CitationType):
    name = _("Thesis/Dissertation")
    detect_re = re.compile(r'\[(Doctoral dissertation|Master[’\']s thesis)\]', re.IGNORECASE)

    def validate(self, text, para, cite):
        if not re.search(r'\]\.\s+', text):
            cite['errors'].append(_("After thesis-type bracket you need ']. ' before institution."))
        # title before the bracket
        m = re.match(r'^(.*?)\s*\[', text)
        if m:
            title = m.group(1).strip()
            if not is_snippet_italic(para, title):
                cite['errors'].append(_("Thesis title must be italicized: '{title}'").format(title=title))

class BookChapterCitation(CitationType):
    name = _("Book Chapter")
    detect_re = re.compile(r'\bIn\s+.+?\(Ed[s]?\.\),.*pp\.\s*\d+', re.IGNORECASE)

    def validate(self, text, para, cite):
        # In Editors (Ed.), Book Title (pp. xx–xx). Publisher.
        m = re.match(
            r'^In\s+(.+?)\s*\(Ed[s]?\.\),\s*'     # editors
            r'(.+?)\s*'                          # book title
            r'\(pp\.\s*(\d+[-–]\d+)\)\.\s*'       # pages
            r'(.+)\.$',                          # publisher
            text
        )
        if not m:
            cite['errors'].append(
                _("Book chapter must be \"In Editor(s) (Ed.), Book Title (pp. xx–xx). Publisher.\"")
            )
            return
        editors, book_title, pages, pub = m.groups()
        if '&' not in editors:
            cite['errors'].append(_("Editors list must include '&' before last editor."))
        if not book_title[0].isupper():
            cite['errors'].append(_("Book title must start with a capital: '{book_title}'").format(book_title=book_title))

        title_main = re.sub(r'\s*\[.*?\]\s*', '', book_title).strip()
        if not is_snippet_italic(para, title_main):
            cite['errors'].append(_("Book title must be italicized."))

        if '-' in pages:
            cite['errors'].append(_("Use en-dash (–)[U+2013], not hyphen (-)[U+002d], in page ranges."))
            pages = pages.replace('-','–')

        if '–' in pages:
            sp, ep = pages.split('–', 1)
        else:
            sp = ep = pages
 
        if int(sp) >= int(ep):
            cite['errors'].append(_("Page start ({sp}) must be less than end ({ep}).").format(sp=sp,ep=ep))
        if not pub.strip():
            cite['errors'].append(_("Publisher missing."))

class EditedBookCitation(CitationType):
    name = _("Edited Book")
    detect_re = re.compile(r'\(Ed[s]?\.\)\.\s*\(\d{4}\)\.', re.IGNORECASE)

    def validate(self, text, para, cite):
        # Author. (Ed.). (YYYY). Title. Publisher.
        m = re.match(
            r'^.+?\(Ed[s]?\.\)\.\s*'   # (Ed.) block
            r'\(\d{4}\)\.\s*'          # (YYYY).
            r'(.+?)\.\s*'              # title
            r'(.+?)\.$',               # publisher
            text
        )
        if not m:
            cite['errors'].append(
                _("Edited book must be \"Author. (Ed.). (YYYY). Title. Publisher.\"")
            )
            return
        title, pub = m.groups()

        title_main = re.sub(r'\s*\[.*?\]\s*', '', title).strip()
        if not is_snippet_italic(para, title_main):
            cite['errors'].append(_("Edited-book title must be italicized."))

class JournalArticleCitation(CitationType):
    name = _("Journal Article")
    # allow both hyphen and en-dash in the page range, and match from start to end
    detect_re = re.compile(
        r'^\s*.+?\(\d{4}\)\.\s*'             # authors + (YYYY).
        r'.+?,\s*'                           # journal name + comma
        r'\d+(?:\(\d+(?:[-–]\d+)?\))?,\s*'    # volume(issue or issue-range),
        r'\d+(?:[-–]\d+)?\.\s*$',             # pages (with hyphen or en-dash)
        re.UNICODE
    )

    def validate(self, text, para, cite):
        # Normalize year part
        year_m = re.search(r'\(\d{4}\)\.\s*', text)
        if not year_m:
            cite['errors'].append(_("Missing '(YYYY).' block."))
            return
        remainder = text[year_m.end():].strip()

        # Split title vs. source
        m1 = re.match(r'(.+?[.!?])\s*(.+)$', remainder)
        if not m1:
            cite['errors'].append(_("Cannot split title and source on punctuation."))
            return
        title_part, source = m1.groups()

        # Updated source regex to allow – or –
        
        m2 = re.match(
            r'^(.+?),\s*'                # 1) journal name
            r'(\d+)'                     # 2) volume
            r'(?:\((\d+(?:[-–]\d+)?)\))?,'   # 3) optional issue
            r'\s*(\d+(?:[-–]\d+)?)\.$',   # 4) pages, hyphen or en-dash
            source
        )
        if not m2:
            cite['errors'].append(_("Source must be 'Journal, Volume(Issue), pp–pp.'"))
            return
        journal, vol, iss, pages = m2.groups()

        # Italics & capitalization checks
        title_main = re.sub(r'\s*\[.*?\]\s*', '', journal).strip()
        if not is_snippet_italic(para, title_main):
            cite['errors'].append(_("Journal title must be italicized: '{journal}'").format(journal=title_main))

        should_cap = []
        for w in journal.split():
            if w in ["of", "by", "between", "and", "or", "on", "&", "in"]:
                continue
            if not w[0].isupper():
                should_cap.append(w)
        if should_cap:
            cite['errors'].append(_("Journal title word not capitalized: '{should_cap}'").format(should_cap=should_cap))

        if not is_snippet_italic(para, vol):
            cite['errors'].append(_("Volume must be italicized: '{vol}'").format(vol=vol))

        if '-' in pages:
            cite['errors'].append(_("Use en-dash (–)[U+2013], not hyphen (-)[U+002d], in page ranges."))
            pages = pages.replace('-','–')

        if iss and '-' in iss:
            cite['errors'].append(_("Use en-dash (–)[U+2013], not hyphen (-)[U+002d], in issue ranges."))
            iss = iss.replace('-','–')

        # Split only if there really is a range
        if '–' in pages:
            sp, ep = pages.split('–', 1)
        else:
            sp = ep = pages

        try:
            sp_i, ep_i = int(sp), int(ep)
            if sp_i <= 0 or ep_i <= 0:
                cite['errors'].append(_("Page numbers must be positive."))
            if sp_i > ep_i:
                cite['errors'].append(_("Start page ({sp_i}) > end page ({ep_i}).").format(sp_i=sp_i,ep_i=ep_i))
        except ValueError:
            cite['errors'].append(_("Page numbers must be integers."))

        # 1) Strip off ending punctuation, then split on “:”
        segments = re.split(r':\s*', title_part.rstrip('.!?'))

        for seg in segments:
            words = seg.split()
            if not words:
                continue

            fw = words[0]
            first_char = fw[0]

            # Allow uppercase English letters, digits, or CJK
            if not (
                first_char.isupper()
                or first_char.isdigit()
                or re.match(r'[\u4E00-\u9FFF]', first_char)
            ):
                cite['errors'].append(_("Article title segment must start uppercase, digit, or CJK: '{fw}'").format(fw=fw))


            # 3) All other words (in this segment) must be lowercase or ALL-CAPS
            for w in words[1:]:
                if w[0].isupper() and not w.isupper():
                    cite['errors'].append(
                        _("Article title word must be lowercase (or ALL-CAPS): '{w}'").format(w=w)
                    )
                    break

class ConferenceCitation(CitationType):
    name = _("Conference Article")
    detect_re = re.compile(r'\]\.\s*.+?,\s*.+\.$')  # loose match after year

    def validate(self, text, para, cite):
        # split off year block
        year_re = re.compile(r'\(\d{4}(?:,\s*[A-Za-z]+ \d{1,2}(?:[-–]\d{1,2})?)?\)\.')
        m0 = year_re.search(text)
        if not m0:
            cite['errors'].append(_("Missing '(YYYY).' block."))
            return
        if '-' in m0.group():
            cite['errors'].append(_("Use en-dash (–)[U+2013], not hyphen (-)[U+002d], in date ranges."))

        rem = text[m0.end():].strip()
        m1 = re.match(r'(.+?[.!?])\s*(.+)$', rem)
        if not m1:
            cite['errors'].append(_("Cannot split title and conference info."))
            return
        title_part, conf_info = m1.groups()
        if not is_snippet_italic(para, title_part):
            cite['errors'].append(_("Conference title must be italicized."))
        # expect "Conference Name, Location."
        if ',' not in conf_info or not conf_info.endswith('.'):
            cite['errors'].append(_("Conference info must be 'Name, Location.'"))

class MonographCitation(CitationType):
    name = _("Monograph/Book")
    detect_re = re.compile(
        r'\(\d{4}\)\.\s*'         # (YYYY).
        r'[^,]+?\.\s*'            # title ending in a period, with no commas
        r'[^,]+?\.$'              # publisher ending in a period, with no commas
    )
    def validate(self, text, para, cite):
        m = re.match(r'^(.+?)\s*\(\d{4}\)\.\s*(.+?)\.\s*(.+?)\.$', text)
        if not m:
            cite['errors'].append(_("Monograph must be 'Author. (YYYY). Title. Publisher.'"))
            return
        year, title, pub = m.groups()
        if pub.isdigit():
            cite['errors'].append(_("Publisher looks numeric, not valid for a book."))

        title_main = re.sub(r'\s*\[.*?\]\s*', '', title).strip()
        if not is_snippet_italic(para, title_main):
            cite['errors'].append(_("Book title must be italicized: '{title}'").format(title=title_main))

# --- Registry and hints --------------------------------------------------

TYPE_CLASSES = [
    ThesisCitation,
    BookChapterCitation,
    EditedBookCitation,
    JournalArticleCitation,
    ConferenceCitation,
    MonographCitation,
]

HINTS = {
    "Thesis/Dissertation": "Ensure the thesis title is italicized and you have ‘]. ’ before the institution name.",
    "Book Chapter": "Use ‘In Editor(s) (Ed.), Book Title (pp. xx–xx). Publisher.’ with italics on the book title.",
    "Edited Book": "Format as 'Author. (Ed.). (YYYY). Title. Publisher.' and italicize the title.",
    "Journal Article": "Italicize the journal title & volume, capitalize only the first word of the article title, and check page numbers.",
    "Conference Article": "Italicize the conference paper title and format 'Conference Name, Location.'",
    "Monograph/Book": "Use 'Author. (YYYY). Title. Publisher.' with the title italicized.",
}
DEFAULT_HINT = _("Make sure this entry matches one of the six APA-7 reference types exactly.")

# --- Other validators -----------------------------------------------------

def validate_authors(text, cite):
    m = re.match(r'^(.+?)\s*\(', text)
    if not m:
        cite['errors'].append(_("Cannot parse authors list."))
        return
    authors_str = m.group(1).strip()
    authors = [a.strip() for a in re.split(r',\s*(?=[A-Z][a-z])', authors_str)]
    n = len(authors)
    if n == 0:
        cite['errors'].append(_("No authors found."))
        return
    if n > 1:
        if '&' not in authors_str:
            cite['errors'].append(_("Multiple authors need '&' before last author."))
        if n <= 20 and not re.search(r',\s*&\s*', authors_str):
            cite['errors'].append(_("Use comma before '&' for 2-20 authors."))
        if n > 20 and '…' not in authors_str:
            cite['errors'].append(_("Use ellipsis after 19 authors when >20 authors."))

def validate_year(text, cite):
    if not re.search(r'\(\d{4}(?:,\s*[A-Za-z]+ \d{1,2}(?:[-–]\d{1,2})?)?\)\.', text):
        cite['errors'].append(_("Year block must be '(YYYY).' or '(YYYY, Month D–D).'"))

def validate_title(text, cite):
    m = re.search(r'\)\.\s*(.+?)(?=[\.\?\!])', text)
    if not m:
        cite['errors'].append(_("Cannot parse title (no sentence-ending punctuation)."))
        return
    title = m.group(1).strip()
    if not (title[0].isupper() or re.match(r'[\d\u4E00-\u9FFF]', title[0])):
        cite['errors'].append(_("Title must start with a capital letter or digit/CJK."))
    if re.search(r'[\u4e00-\u9fff]', title) and not re.search(r'\[.+?\]', title):
        cite['errors'].append(_("Chinese title needs English translation in [ ] immediately after."))

# --- Core source validation using type detection -------------------------

def validate_source(text, para, cite):
    for cls in TYPE_CLASSES:
        if cls.detect(text):
            cite['detected_type'] = cls.name
            cls().validate(text, para, cite)
            return
    cite['errors'].append(_("Couldn't recognize as any of the six APA-7 types."))

# --- Diagnose functions --------------------------------------------------

def diagnose_entry(para, text, idx):
    cite = {'raw': text, 'errors': []}

    # Run all the validators 
    validate_authors(text, cite)
    validate_year(text, cite)
    validate_title(text, cite)
    validate_source(text, para, cite)

    # Generic trailing-period check (still on the original, or norm—they're equivalent now)
    if not text.endswith('.'):
        cite['errors'].append(_("Reference must end with a period."))


    fmt = para.paragraph_format
    if fmt.line_spacing and fmt.line_spacing != 1:
        cite['errors'].append(_("Line spacing must be single."))
    if round(fmt.left_indent.cm, 2) != 0.7 or round(fmt.first_line_indent.cm, 2) != -0.7:
        cite['errors'].append(_("Paragraph must have hanging indent of 0.7 cm."))
    for run in para.runs:
        font = run.font
        if font.name and font.name != 'Times New Roman':
            cite['errors'].append(_("Font must be Times New Roman."))
            break
        if font.size and font.size.pt != 12:
            cite['errors'].append(_("Font size must be 12 pt."))
            break

    # 4) Print errors & hint
    if cite['errors']:
        
        # Header: entry number & type
        # 1) pull out the raw type (or fallback to 'Unknown')
        raw_type = cite.get('detected_type', _('Unknown'))

        # 2) translate the type itself
        localized_type = _(raw_type)

        # 3) translate the template, then format in Python
        template = _("Entry {idx} ({typ}): ")
        header = Text(
            template.format(idx=idx, typ=localized_type),
            style="bold cyan"
        )
        header.append(text)
        console.print(header)

        # Each error in red
        for err in cite['errors']:
            console.print("  • " + err, style="red")

        # instead of the old hint, do this:
        tpl = HINT_TEMPLATES.get(cite.get('detected_type'))
        if tpl:
            # prints the example with only the needed parts in italic
            console.print(tpl(), style="magenta")
        else:
            console.print(Text(f"Hint: {HINTS.get(cite.get('detected_type'), DEFAULT_HINT)}", 
                               style="italic magenta"))
        console.print()
        return 1
    return 0


def diagnose(docx_path):
    doc = Document(docx_path)
    entries = get_bibliography_paragraphs(doc)

    # Alphabetical check
    surnames = [txt.split(',',1)[0].lower() for _, txt in entries]
    if surnames != sorted(surnames):
        console.print(_("⚠️ Entries are not in alphabetical order by surname.\n"), style="yellow")

    # Validate each
    errors = 0
    for i, (para, txt) in enumerate(entries, 1):
        errors += diagnose_entry(para, txt, i)

    # Summary
    if errors:
        console.print(_("Total entries with errors: {errors}").format(errors=errors), style="bold red")
    else:
        console.print(_("✅ All entries look good!"), style="bold green")

def setup_gettext(lang_code: str):
    try:
        tr = gettext.translation(
            domain='apa7_bib_validator',
            localedir='locales',
            languages=[lang_code]
        )
        tr.install()
        global _
        _ = tr.gettext
    except FileNotFoundError:
        # fallback to no-op _()
        gettext.install(domain='apa7_bib_validator')
        _ = gettext.gettext

def main():
    parser = argparse.ArgumentParser(
        description="Validate APA-7 bibliography entries in a .docx file."
    )
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

    args = parser.parse_args()
    setup_gettext(args.lang)
    diagnose(args.docx_path)

if __name__ == '__main__':
    main()