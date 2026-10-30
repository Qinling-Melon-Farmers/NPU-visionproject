"""Formatting helpers for the multimedia vision report.

The module keeps OOXML details in one place so the content builder stays readable.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

CN_FONT = "宋体"
CN_HEAD = "黑体"
EN_FONT = "Times New Roman"
CODE_FONT = "Consolas"
TEXT_WIDTH_CM = 14.6
TEXT_SIZE = 10.5  # 正文五号，4~8 页紧凑报告
BLACK = RGBColor(0, 0, 0)
GRAY = RGBColor(0x59, 0x59, 0x59)


# ---------------------------------------------------------------------------
# low level OOXML
# ---------------------------------------------------------------------------

def _set_run_fonts(run, name: str, size: float | None = None, bold: bool | None = None,
                   color: RGBColor | None = None, italic: bool | None = None):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    rfonts.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color
        color_el = rpr.find(qn("w:color"))
        if color_el is not None:
            for attr in ("w:themeColor", "w:themeShade", "w:themeTint"):
                if color_el.get(qn(attr)) is not None:
                    del color_el.attrib[qn(attr)]


def _clear_theme_color(style):
    rpr = style.element.rPr
    if rpr is None:
        return
    color = rpr.find(qn("w:color"))
    if color is not None:
        for attr in ("w:themeColor", "w:themeShade", "w:themeTint"):
            if color.get(qn(attr)) is not None:
                del color.attrib[qn(attr)]
        color.set(qn("w:val"), "000000")


def _set_first_line_chars(paragraph_or_style, chars: int = 2):
    element = getattr(paragraph_or_style, "element", None)
    if element is None:
        element = paragraph_or_style._element
    ppr = element.get_or_add_pPr()
    ind = ppr.find(qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        ppr.append(ind)
    ind.set(qn("w:firstLineChars"), str(chars * 100))
    ind.set(qn("w:firstLine"), str(chars * 240))  # 12 pt * 20 twips


def _set_outline_level(style, level: int):
    ppr = style.element.get_or_add_pPr()
    outline = ppr.find(qn("w:outlineLvl"))
    if outline is None:
        outline = OxmlElement("w:outlineLvl")
        ppr.append(outline)
    outline.set(qn("w:val"), str(level))


def _remove_borders(element):
    ppr = element.get_or_add_pPr()
    for old in ppr.findall(qn("w:pBdr")):
        ppr.remove(old)


# ---------------------------------------------------------------------------
# document / styles
# ---------------------------------------------------------------------------

def setup_document() -> Document:
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(3.17)
    section.right_margin = Cm(3.17)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.header_distance = Cm(1.5)
    section.footer_distance = Cm(1.75)

    normal = doc.styles["Normal"]
    normal.font.name = CN_FONT
    normal.font.size = Pt(12)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), CN_FONT)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    _set_first_line_chars(normal, 2)

    specs = {
        "Heading 1": (16, 18, 12, 0),
        "Heading 2": (14, 12, 6, 1),
        "Heading 3": (12, 6, 3, 2),
    }
    for name, (size, before, after, outline) in specs.items():
        style = doc.styles[name]
        style.font.name = CN_HEAD
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = BLACK
        style.element.rPr.rFonts.set(qn("w:eastAsia"), CN_HEAD)
        _clear_theme_color(style)
        pf = style.paragraph_format
        pf.space_before = Pt(before)
        pf.space_after = Pt(after)
        pf.first_line_indent = Pt(0)
        pf.keep_with_next = True
        pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
        _set_outline_level(style, outline)
        if name == "Heading 1":
            pf.page_break_before = True

    caption = doc.styles["Caption"]
    caption.font.name = CN_FONT
    caption.font.size = Pt(10.5)
    caption.font.bold = False
    caption.font.color.rgb = BLACK
    caption.element.rPr.rFonts.set(qn("w:eastAsia"), CN_FONT)
    _clear_theme_color(caption)
    cpf = caption.paragraph_format
    cpf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cpf.first_line_indent = Pt(0)
    cpf.space_before = Pt(4)
    cpf.space_after = Pt(4)
    cpf.line_spacing = 1.15

    if "Transcript Title" not in [s.name for s in doc.styles]:
        tr = doc.styles.add_style("Transcript Title", WD_STYLE_TYPE.PARAGRAPH)
        tr.base_style = doc.styles["Normal"]
        tr.font.name = CN_FONT
        tr.font.size = Pt(11)
        tr.font.bold = True
        tr.font.color.rgb = BLACK
        tr.element.rPr.rFonts.set(qn("w:eastAsia"), CN_FONT)
        tr.paragraph_format.space_before = Pt(6)
        tr.paragraph_format.space_after = Pt(3)
        tr.paragraph_format.first_line_indent = Pt(0)
        tr.paragraph_format.keep_with_next = True
        _set_outline_level(tr, 9)

    if "Code Block" not in [s.name for s in doc.styles]:
        code = doc.styles.add_style("Code Block", WD_STYLE_TYPE.PARAGRAPH)
        code.base_style = doc.styles["Normal"]
        code.font.name = CODE_FONT
        code.font.size = Pt(8.5)
        code.element.rPr.rFonts.set(qn("w:eastAsia"), CN_FONT)
        code.paragraph_format.line_spacing = 1.0
        code.paragraph_format.space_before = Pt(0)
        code.paragraph_format.space_after = Pt(0)
        code.paragraph_format.first_line_indent = Pt(0)
        code.paragraph_format.left_indent = Cm(0.25)
        code.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        ppr = code.element.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "F7F7F7")
        ppr.append(shd)

    return doc


def set_core_properties(doc: Document):
    cp = doc.core_properties
    cp.author = "肖怀瑾"
    cp.last_modified_by = "肖怀瑾"
    cp.title = "多媒体技术语音大作业报告"
    cp.subject = "从零训练关键词唤醒模型（KWS）"
    cp.keywords = "关键词唤醒；KWS；Speech Commands；DS-CNN；log-Mel"
    cp.comments = ""
    cp.category = "课程实验报告"


def enable_field_update(doc: Document):
    settings = doc.settings.element
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    settings.append(update)


# ---------------------------------------------------------------------------
# sections, headers, footers
# ---------------------------------------------------------------------------

def new_section(doc: Document):
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(3.17)
    section.right_margin = Cm(3.17)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.header_distance = Cm(1.5)
    section.footer_distance = Cm(1.75)
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False
    return section


def set_page_number_format(section, fmt: str | None = None, start: int = 1):
    sect_pr = section._sectPr
    for old in sect_pr.findall(qn("w:pgNumType")):
        sect_pr.remove(old)
    pg = OxmlElement("w:pgNumType")
    if fmt:
        pg.set(qn("w:fmt"), fmt)
    pg.set(qn("w:start"), str(start))
    cols = sect_pr.find(qn("w:cols"))
    if cols is not None:
        cols.addprevious(pg)
    else:
        sect_pr.append(pg)


def add_field(paragraph, code: str, placeholder: str = "1"):
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {code} "
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = placeholder
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for el in (begin, instr, sep, text, end):
        run._r.append(el)


def add_header(section, text: str):
    section.header.is_linked_to_previous = False
    paragraph = section.header.paragraphs[0]
    paragraph.text = ""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = paragraph.add_run(text)
    _set_run_fonts(run, CN_FONT, 9, False, GRAY)
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "BFBFBF")
    pbdr.append(bottom)
    ppr.append(pbdr)


def add_footer_page_x_of_y(section):
    section.footer.is_linked_to_previous = False
    paragraph = section.footer.paragraphs[0]
    paragraph.text = ""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("第 ")
    _set_run_fonts(run, CN_FONT, 9)
    add_field(paragraph, "PAGE", "1")
    run = paragraph.add_run(" 页  共 ")
    _set_run_fonts(run, CN_FONT, 9)
    add_field(paragraph, "NUMPAGES", "1")
    run = paragraph.add_run(" 页")
    _set_run_fonts(run, CN_FONT, 9)


def add_footer_roman(section):
    section.footer.is_linked_to_previous = False
    paragraph = section.footer.paragraphs[0]
    paragraph.text = ""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_field(paragraph, "PAGE", "I")


def add_page_break(doc: Document):
    doc.add_page_break()


# ---------------------------------------------------------------------------
# headings, paragraphs, captions
# ---------------------------------------------------------------------------

def heading(doc: Document, text: str, level: int = 1):
    paragraph = doc.add_paragraph(style=f"Heading {level}")
    paragraph.add_run(text)
    return paragraph


def body(doc: Document, text: str, first_line: bool = True):
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    _set_run_fonts(run, CN_FONT, TEXT_SIZE)
    if first_line:
        _set_first_line_chars(paragraph, 2)
    return paragraph


def body_no_indent(doc: Document, text: str):
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    _set_run_fonts(run, CN_FONT, TEXT_SIZE)
    paragraph.paragraph_format.first_line_indent = Pt(0)
    return paragraph


def bullet(doc: Document, text: str):
    paragraph = doc.add_paragraph(style="List Bullet")
    run = paragraph.add_run(text)
    _set_run_fonts(run, CN_FONT, TEXT_SIZE)
    paragraph.paragraph_format.first_line_indent = Pt(0)
    return paragraph


def caption(doc: Document, kind: str, number: int, text: str, above: bool):
    paragraph = doc.add_paragraph(style="Caption")
    run = paragraph.add_run(f"{kind} {number}")
    _set_run_fonts(run, CN_FONT, 10.5, True, BLACK)
    run = paragraph.add_run(f"  {text}")
    _set_run_fonts(run, CN_FONT, 10.5, False, BLACK)
    paragraph.paragraph_format.keep_with_next = above
    return paragraph


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------

def _set_table_width(table, widths_cm: list[float]):
    tbl_pr = table._tbl.tblPr
    for old in tbl_pr.findall(qn("w:tblW")):
        tbl_pr.remove(old)
    for old in tbl_pr.findall(qn("w:tblLayout")):
        tbl_pr.remove(old)
    tbl_w = OxmlElement("w:tblW")
    tbl_w.set(qn("w:w"), str(int(sum(widths_cm) * 567)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_pr.append(tbl_w)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)
    grid = table._tbl.tblGrid
    for grid_col, width in zip(grid.gridCol_lst, widths_cm):
        grid_col.set(qn("w:w"), str(int(width * 567)))
    for row in table.rows:
        for cell, width in zip(row.cells, widths_cm):
            cell.width = Cm(width)


def _set_table_borders(table):
    table.style = "Normal Table"
    tbl_pr = table._tbl.tblPr
    for old in tbl_pr.findall(qn("w:tblLook")):
        tbl_pr.remove(old)
    look = OxmlElement("w:tblLook")
    look.set(qn("w:val"), "0000")
    for attr in ("firstRow", "lastRow", "firstColumn", "lastColumn", "noHBand", "noVBand"):
        look.set(qn(f"w:{attr}"), "0")
    tbl_pr.append(look)
    for old in tbl_pr.findall(qn("w:tblBorders")):
        tbl_pr.remove(old)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        if edge in ("top", "bottom"):
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), "12")
        else:
            el.set(qn("w:val"), "none")
            el.set(qn("w:sz"), "0")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000" if edge in ("top", "bottom") else "auto")
        borders.append(el)
    tbl_pr.append(borders)


def _set_cell_bottom_border(cell, sz: int = 6):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(sz))
    bottom.set(qn("w:space"), "0")
    bottom.set(qn("w:color"), "000000")
    borders.append(bottom)


def _nil_cell_borders(cell):
    tc_pr = cell._tc.get_or_add_tcPr()
    for old in tc_pr.findall(qn("w:tcBorders")):
        tc_pr.remove(old)
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tc_pr.append(borders)


def _shade(cell, fill: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def _cell_margins(table, top=30, bottom=30, left=70, right=70):
    tbl_pr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for edge, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:w"), str(value))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tbl_pr.append(mar)


def _repeat_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def _cant_split(row):
    tr_pr = row._tr.get_or_add_trPr()
    cant = OxmlElement("w:cantSplit")
    tr_pr.append(cant)


def add_table(doc: Document, number: int, caption_text: str, headers: list[str],
              rows: list[list], widths: list[float], numeric_cols: set[int] | None = None,
              font_size: float = 9, align_center_cols: set[int] | None = None,
              keep_rows: bool = False):
    caption(doc, "表", number, caption_text, above=True)
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    _set_table_width(table, widths)
    _set_table_borders(table)
    _cell_margins(table)
    numeric_cols = numeric_cols or set()
    align_center_cols = align_center_cols or set()

    header_cells = table.rows[0].cells
    for index, (cell, value) in enumerate(zip(header_cells, headers)):
        cell.text = ""
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.first_line_indent = Pt(0)
        run = paragraph.add_run(str(value))
        _set_run_fonts(run, CN_FONT, font_size, True, BLACK)
        _shade(cell, "F2F2F2")
        _set_cell_bottom_border(cell, 6)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    _repeat_header(table.rows[0])

    for row_values in rows:
        row = table.add_row()
        if keep_rows:
            _cant_split(row)
        for index, (cell, value) in enumerate(zip(row.cells, row_values)):
            cell.text = ""
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.first_line_indent = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.05
            paragraph.paragraph_format.space_after = Pt(0)
            if index in numeric_cols:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            elif index in align_center_cols:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = paragraph.add_run(str(value))
            _set_run_fonts(run, CN_FONT, font_size, False, BLACK)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    # remove any style-inherited cell borders, then restore the header rule
    for row in table.rows:
        for cell in row.cells:
            _nil_cell_borders(cell)
    for cell in table.rows[0].cells:
        _set_cell_bottom_border(cell, 6)

    # small spacer
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after = Pt(2)
    spacer.paragraph_format.line_spacing = 1.0
    return table


def add_figure(doc: Document, number: int, path: str | Path, caption_text: str,
               width_cm: float = 14.5):
    path = Path(path)
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = Pt(0)
    paragraph.paragraph_format.space_before = Pt(6)
    paragraph.paragraph_format.space_after = Pt(2)
    paragraph.paragraph_format.keep_with_next = True
    run = paragraph.add_run()
    if not path.is_file():
        raise FileNotFoundError(path)
    run.add_picture(str(path), width=Cm(width_cm))
    caption(doc, "图", number, caption_text, above=False)


# ---------------------------------------------------------------------------
# boxes and code
# ---------------------------------------------------------------------------

def add_box(doc: Document, lines: list[str], fill: str = "F3F4F6",
            border_color: str = "7F7F7F", font_size: float = 10,
            label: str | None = None, keep_together: bool = True):
    table = doc.add_table(rows=1, cols=1)
    table.style = "Normal Table"
    table.autofit = False
    _set_table_width(table, [TEXT_WIDTH_CM])
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "auto")
        borders.append(el)
    tbl_pr.append(borders)
    cell = table.rows[0].cells[0]
    _shade(cell, fill)
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = OxmlElement("w:tcBorders")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "18")
    left.set(qn("w:space"), "0")
    left.set(qn("w:color"), border_color)
    tc_borders.append(left)
    tc_pr.append(tc_borders)
    _cell_margins(table, top=60, bottom=60, left=100, right=100)
    if keep_together:
        _cant_split(table.rows[0])

    first = True
    if label:
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.first_line_indent = Pt(0)
        paragraph.paragraph_format.space_after = Pt(2)
        run = paragraph.add_run(label)
        _set_run_fonts(run, CN_FONT, font_size - 0.5, True, GRAY)
        first = False
    for line in lines:
        paragraph = cell.paragraphs[0] if first else cell.add_paragraph()
        first = False
        paragraph.paragraph_format.first_line_indent = Pt(0)
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.paragraph_format.line_spacing = 1.15
        line = line.rstrip()
        if line.startswith("#"):
            line = line.lstrip("#").strip()
            _add_inline(paragraph, line, font_size + 0.5, bold=True)
        elif line.startswith(("- ", "* ")):
            _add_inline(paragraph, "· " + line[2:], font_size)
        else:
            _add_inline(paragraph, line, font_size)
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after = Pt(2)
    spacer.paragraph_format.line_spacing = 1.0


def add_code_block(doc: Document, text: str):
    for line in text.split("\n"):
        paragraph = doc.add_paragraph(style="Code Block")
        run = paragraph.add_run(line if line else " ")
        _set_run_fonts(run, CODE_FONT, 8.5, False, BLACK)


# ---------------------------------------------------------------------------
# markup / latex
# ---------------------------------------------------------------------------

_SUPER = str.maketrans("0123456789-+", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺")


def _convert_math(value: str) -> str:
    value = value.replace("\\times", "×").replace("\\cdot", "·")
    value = value.replace("\\approx", "≈").replace("\\leq", "≤").replace("\\geq", "≥")
    value = value.replace("\\%", "%").replace("\\,", " ").replace("\\;", " ")
    value = value.replace("\\text{", "").replace("}", "")
    value = re.sub(r"\^\{?(-?\d+)\}?", lambda m: m.group(1).translate(_SUPER), value)
    value = value.replace("{", "").replace("}", "")
    return value


def clean_latex(text: str) -> str:
    text = re.sub(r"\\\((.*?)\\\)", lambda m: _convert_math(m.group(1)), text, flags=re.S)
    text = re.sub(r"\\\[(.*?)\\\]", lambda m: _convert_math(m.group(1)), text, flags=re.S)
    text = text.replace("<proposed_plan>", "").replace("</proposed_plan>", "")
    text = text.replace("\r\n", "\n")
    return text


_INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")


def _add_inline(paragraph, text: str, size: float, bold: bool = False):
    text = clean_latex(text)
    parts = _INLINE.split(text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            run = paragraph.add_run(part[2:-2])
            _set_run_fonts(run, CN_FONT, size, True, BLACK)
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            run = paragraph.add_run(part[1:-1])
            _set_run_fonts(run, CODE_FONT, size - 0.5, False, BLACK)
        elif part.startswith("[") and "](" in part and part.endswith(")"):
            label = part[1:part.index("](")]
            run = paragraph.add_run(label)
            _set_run_fonts(run, CN_FONT, size, bold, BLACK)
        else:
            run = paragraph.add_run(part)
            _set_run_fonts(run, CN_FONT, size, bold, BLACK)


def add_markup(doc: Document, text: str, size: float = 10):
    """Render a lightweight subset of Markdown into body paragraphs."""
    text = clean_latex(text)
    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        if not line.strip():
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.first_line_indent = Pt(0)
            paragraph.paragraph_format.space_after = Pt(0)
            continue
        heading_match = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading_match:
            line = heading_match.group(2)
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.first_line_indent = Pt(0)
            paragraph.paragraph_format.space_before = Pt(6)
            paragraph.paragraph_format.space_after = Pt(2)
            _add_inline(paragraph, line, size + 0.5, bold=True)
            continue
        if line.startswith(("- ", "* ")):
            line = "· " + line[2:]
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.first_line_indent = Pt(0)
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.paragraph_format.line_spacing = 1.15
        _add_inline(paragraph, line, size)


# ---------------------------------------------------------------------------
# bookmarks / page refs
# ---------------------------------------------------------------------------

_BOOKMARK_ID = [1000]


def add_bookmark(paragraph, name: str):
    _BOOKMARK_ID[0] += 1
    bookmark_id = str(_BOOKMARK_ID[0])
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), bookmark_id)
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), bookmark_id)
    paragraph._p.insert(0, start)
    paragraph._p.append(end)


def add_pageref(paragraph, name: str):
    add_field(paragraph, f"PAGEREF {name} \\h", "—")


# ---------------------------------------------------------------------------
# cover helpers
# ---------------------------------------------------------------------------

def cover_line(doc: Document, text: str, size: float, bold: bool = False,
               font: str = CN_FONT, space_after: float = 0):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = Pt(0)
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(space_after)
    paragraph.paragraph_format.line_spacing = 1.0
    run = paragraph.add_run(text)
    _set_run_fonts(run, font, size, bold, BLACK)
    return paragraph


def cover_info_table(doc: Document, items: list[tuple[str, str]]):
    table = doc.add_table(rows=0, cols=2)
    table.style = "Normal Table"
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_width(table, [4.2, 8.4])
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "auto")
        borders.append(el)
    tbl_pr.append(borders)
    _cell_margins(table, top=50, bottom=50, left=40, right=40)
    for label, value in items:
        row = table.add_row()
        for index, (cell, text) in enumerate(zip(row.cells, (label, value))):
            cell.text = ""
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.first_line_indent = Pt(0)
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT if index else WD_ALIGN_PARAGRAPH.RIGHT
            run = paragraph.add_run(text)
            _set_run_fonts(run, CN_FONT, 14, False, BLACK)


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------

def inspect(doc: Document, path: Path):
    print(f"saved {path}")
    print(f"paragraphs={len(doc.paragraphs)} tables={len(doc.tables)} images={len(doc.inline_shapes)}")
    text = "\n".join(p.text for p in doc.paragraphs)
    for token in ("解析错误", "python-docx", "Chris Green", "**", "\\(", "rel=True"):
        print(f"token {token!r}: {text.count(token)}")
