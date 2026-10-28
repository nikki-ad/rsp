"""Compose class worksheets using RSP's existing dependency-free XLSX exporter."""
import re
from math import ceil
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import quoteattr

from .xlsx_export import build_routine_report_xlsx


INVALID_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")
INVALID_SHEET = re.compile(r"[\\/*?:\[\]]")
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def unique_sheet_name(name, used):
    base = INVALID_SHEET.sub("-", INVALID_XML.sub("", str(name))).replace("\n", " ").replace("\r", " ").replace("\t", " ").strip().strip("'") or "کلاس"
    base = base[:31].rstrip("'") or "کلاس"
    candidate, suffix = base, 1
    while candidate.casefold() in used:
        suffix += 1
        tail = f" ({suffix})"
        candidate = base[:31-len(tail)].rstrip("'") + tail
    used.add(candidate.casefold())
    return candidate


def build_deficiency_report_xlsx(class_sheets):
    """class_sheets is an iterable of (class/year label, four-column rows)."""
    headers = ["نام دانش‌آموز", "نام درس", "تاریخ ثبت نقص تکلیف", "نام معلم"]
    output = BytesIO()
    sheet_elements, relationships, overrides, used = [], [], [], set()
    styles = None
    with ZipFile(output, "w", ZIP_DEFLATED) as target:
        for index, (label, rows) in enumerate(class_sheets, 1):
            name = unique_sheet_name(label, used)
            clean_rows = ([INVALID_XML.sub("", str(value)) for value in row] for row in rows)
            # The existing writer stores text as inline strings, including values beginning '='.
            with ZipFile(BytesIO(build_routine_report_xlsx(headers, clean_rows))) as source:
                sheet = ET.fromstring(source.read("xl/worksheets/sheet1.xml"))
                for column, width in zip(sheet.find(f"{{{MAIN_NS}}}cols"), [32, 32, 26, 32]):
                    column.set("width", str(width))
                for row in sheet.find(f"{{{MAIN_NS}}}sheetData"):
                    lines = max((sum(max(1, ceil(len(part) / 22)) for part in "".join(cell.itertext()).splitlines()) for cell in row), default=1)
                    row.set("ht", str(min(409, max(36, lines * 18))))
                    row.set("customHeight", "1")
                target.writestr(f"xl/worksheets/sheet{index}.xml", ET.tostring(sheet, encoding="utf-8", xml_declaration=True))
                if styles is None:
                    styles = source.read("xl/styles.xml").replace(b'vertical="center"', b'vertical="center" wrapText="1"')
            sheet_elements.append(f'<sheet name={quoteattr(name)} sheetId="{index}" r:id="rId{index}"/>')
            relationships.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>')
            overrides.append(f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        if not sheet_elements:
            raise ValueError("At least one worksheet is required")
        relationships.append('<Relationship Id="styles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
        prefix = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        target.writestr("xl/styles.xml", styles)
        target.writestr("xl/workbook.xml", prefix + f'<workbook xmlns="{MAIN_NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{"".join(sheet_elements)}</sheets></workbook>')
        target.writestr("xl/_rels/workbook.xml.rels", prefix + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(relationships) + '</Relationships>')
        target.writestr("_rels/.rels", prefix + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        target.writestr("[Content_Types].xml", prefix + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' + "".join(overrides) + '</Types>')
    return output.getvalue()
