from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"a": MAIN_NS, "r": REL_NS, "pr": PKG_REL_NS}

SUPPORTED_BALANZ_SHEETS = (
    "resultados_por_lotes_finales",
    "resultados_por_lotes_iniciales",
)


@dataclass
class BalanzPositionDraft:
    row_number: int
    instrument_type: str
    symbol: str
    quantity: float
    purchase_date: date
    purchase_price: float
    purchase_currency: str
    underlying_ticker: str | None = None
    notes: str = ""


@dataclass
class BalanzImportSkip:
    row_number: int
    ticker: str | None
    reason: str


@dataclass
class BalanzParseResult:
    source_sheet: str
    positions: list[BalanzPositionDraft]
    skipped: list[BalanzImportSkip]


def parse_balanz_extract(workbook_bytes: bytes) -> BalanzParseResult:
    if not workbook_bytes:
        raise ValueError("El archivo de Balanz llegó vacío.")

    try:
        with ZipFile(BytesIO(workbook_bytes)) as archive:
            shared_strings = _read_shared_strings(archive)
            sheet_name, sheet_path = _resolve_balanz_sheet(archive)
            rows = _read_sheet_rows(archive, sheet_path, shared_strings)
    except BadZipFile as exc:
        raise ValueError("El archivo no es un XLSX válido.") from exc
    except KeyError as exc:
        raise ValueError("El extracto de Balanz no tiene la estructura esperada.") from exc

    if not rows:
        raise ValueError("El extracto de Balanz no contiene filas legibles.")

    header = {column_name.strip(): cell_ref for column_name, cell_ref in rows[0].items() if column_name}
    required_columns = {"Cantidad", "Fecha", "Moneda", "Precio Compra", "Ticker", "Tipo", "Descripcion"}
    missing_columns = sorted(required_columns - set(header.keys()))
    if missing_columns:
        raise ValueError(
            f"El extracto no trae las columnas requeridas para importar posiciones: {missing_columns}."
        )

    positions: list[BalanzPositionDraft] = []
    skipped: list[BalanzImportSkip] = []
    for index, row in enumerate(rows[1:], start=2):
        ticker = _upper_string_value(row.get("Ticker"))
        quantity_raw = row.get("Cantidad")
        if not ticker and quantity_raw in (None, ""):
            continue

        instrument_type = _normalize_instrument_type(row.get("Tipo"))
        if instrument_type is None:
            skipped.append(
                BalanzImportSkip(
                    row_number=index,
                    ticker=ticker or None,
                    reason=f"Tipo no soportado en v1: {_text_value(row.get('Tipo')) or 'vacío'}.",
                )
            )
            continue

        try:
            quantity = _float_value(row.get("Cantidad"))
            purchase_price = _float_value(row.get("Precio Compra"))
            purchase_date = _date_value(row.get("Fecha"))
            purchase_currency = _normalize_currency(row.get("Moneda"))
        except ValueError as exc:
            skipped.append(
                BalanzImportSkip(
                    row_number=index,
                    ticker=ticker or None,
                    reason=str(exc),
                )
            )
            continue

        if not ticker:
            skipped.append(
                BalanzImportSkip(
                    row_number=index,
                    ticker=None,
                    reason="Fila sin ticker legible.",
                )
            )
            continue

        if quantity <= 0 or purchase_price <= 0:
            skipped.append(
                BalanzImportSkip(
                    row_number=index,
                    ticker=ticker,
                    reason="Cantidad o precio de compra no son positivos.",
                )
            )
            continue

        description = _text_value(row.get("Descripcion"))
        positions.append(
            BalanzPositionDraft(
                row_number=index,
                instrument_type=instrument_type,
                symbol=ticker,
                quantity=quantity,
                purchase_date=purchase_date,
                purchase_price=purchase_price,
                purchase_currency=purchase_currency,
                underlying_ticker=ticker,
                notes=f"Importado desde Balanz · {description}".strip(),
            )
        )

    return BalanzParseResult(
        source_sheet=sheet_name,
        positions=positions,
        skipped=skipped,
    )


def _read_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for node in root.findall("a:si", NS):
        values.append("".join(text.text or "" for text in node.iterfind(".//a:t", NS)))
    return values


def _resolve_balanz_sheet(archive: ZipFile) -> tuple[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        relation.attrib["Id"]: relation.attrib["Target"]
        for relation in rels_root.findall("pr:Relationship", NS)
    }
    sheets = workbook.find("a:sheets", NS)
    if sheets is None:
        raise KeyError("Workbook sin hojas.")

    available: list[tuple[str, str]] = []
    for sheet in sheets.findall("a:sheet", NS):
        name = sheet.attrib.get("name", "")
        rel_id = sheet.attrib.get(f"{{{REL_NS}}}id")
        if not rel_id or rel_id not in rel_map:
            continue
        target = rel_map[rel_id]
        normalized = str(PurePosixPath("xl") / PurePosixPath(target))
        available.append((name, normalized))

    for supported_name in SUPPORTED_BALANZ_SHEETS:
        for name, target in available:
            if name == supported_name:
                return name, target

    if available:
        first_name, first_target = available[0]
        return first_name, first_target
    raise KeyError("No se encontraron hojas en el workbook.")


def _read_sheet_rows(archive: ZipFile, sheet_path: str, shared_strings: list[str]) -> list[dict[str, object]]:
    root = ET.fromstring(archive.read(sheet_path))
    rows: list[dict[str, object]] = []
    for row in root.findall(".//a:sheetData/a:row", NS):
        parsed: dict[str, object] = {}
        for cell in row.findall("a:c", NS):
            reference = cell.attrib.get("r", "")
            column = "".join(char for char in reference if char.isalpha())
            parsed[column] = _cell_value(cell, shared_strings)
        rows.append(_map_row_columns(parsed))
    return rows


def _cell_value(cell, shared_strings: list[str]) -> object:
    cell_type = cell.attrib.get("t")
    value_node = cell.find("a:v", NS)
    inline_node = cell.find("a:is", NS)

    if cell_type == "inlineStr" and inline_node is not None:
        return "".join(text.text or "" for text in inline_node.iterfind(".//a:t", NS))

    if value_node is None:
        return ""

    raw_value = value_node.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)]
        except (ValueError, IndexError):
            return raw_value
    return raw_value


def _map_row_columns(parsed: dict[str, object]) -> dict[str, object]:
    if not parsed:
        return {}
    ordered_columns = sorted(parsed.keys(), key=_column_to_index)
    values = [parsed[column] for column in ordered_columns]
    return {str(values[index]).strip(): values[index] for index in range(len(values))} if _looks_like_header(values) else {
        _header_name_for_column(column_index): values[idx]
        for idx, column_index in enumerate(ordered_columns)
    }


BALANZ_COLUMN_MAP = {
    "A": "Cantidad",
    "B": "Descripcion",
    "C": "Fecha",
    "D": "Fecha Lote",
    "E": "Gastos",
    "F": "Moneda",
    "G": "Operacion",
    "H": "Precio Compra",
    "I": "Ticker",
    "J": "Tipo",
    "K": "DolarCCL",
    "L": "DolarMEP",
    "M": "DolarOficial",
}


def _header_name_for_column(column_name: str) -> str:
    return BALANZ_COLUMN_MAP.get(column_name, column_name)


def _looks_like_header(values: list[object]) -> bool:
    normalized = [str(value).strip() for value in values]
    return "Cantidad" in normalized and "Ticker" in normalized and "Tipo" in normalized


def _column_to_index(column_name: str) -> int:
    value = 0
    for char in column_name:
        value = (value * 26) + (ord(char.upper()) - 64)
    return value


def _text_value(value: object) -> str:
    return str(value or "").strip()


def _upper_string_value(value: object) -> str:
    return _text_value(value).upper()


def _float_value(value: object) -> float:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Faltan datos numéricos en una fila del extracto.")
    if "." in raw and "," in raw:
        normalized = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        normalized = raw.replace(",", ".")
    else:
        normalized = raw
    try:
        return float(normalized)
    except ValueError as exc:
        raise ValueError(f"No se pudo interpretar un número del extracto: {raw}.") from exc


def _date_value(value: object) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Falta la fecha de compra en una fila del extracto.")
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        pass
    try:
        excel_serial = float(raw)
    except ValueError as exc:
        raise ValueError(f"No se pudo interpretar la fecha del extracto: {raw}.") from exc
    return (datetime(1899, 12, 30) + timedelta(days=excel_serial)).date()


def _normalize_currency(value: object) -> str:
    raw = str(value or "").strip().lower()
    if "peso" in raw:
        return "ARS"
    if "dolar" in raw or "usd" in raw:
        return "USD"
    raise ValueError(f"Moneda no soportada en el extracto: {value}.")


def _normalize_instrument_type(value: object) -> str | None:
    raw = str(value or "").strip().lower()
    if "cedear" in raw:
        return "cedear"
    if "accion" in raw or "stock" in raw:
        return "stock"
    return None
