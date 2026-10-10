"""Validate an uploaded synthetic full snapshot without writing anything."""

import csv
import io
from dataclasses import dataclass
from datetime import date
import hashlib
import json

import pandas as pd

from src.data_loader import REQUIRED_COLUMNS


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
REQUIRED_VALUES = (
    "PA_Request_ID", "Received_Date", "Procedure_Category", "Request_Type",
    "Status", "Documentation_Status", "Additional_Info_Requested", "Resubmission_Count",
)
ALLOWED_VALUES = {
    "Status": {"Approved", "Denied", "Pending"},
    "Request_Type": {"Standard", "Expedited"},
    "Documentation_Status": {"Complete", "Incomplete"},
    "Additional_Info_Requested": {"Yes", "No"},
}


@dataclass
class ValidationResult:
    frame: pd.DataFrame | None
    errors: list[str]
    warnings: list[str]

    @property
    def valid(self) -> bool:
        return self.frame is not None and not self.errors


def _positions(mask: pd.Series) -> str:
    """Use request-row positions, not physical CSV lines with quoted text."""
    return ", ".join(str(i + 1) for i in mask[mask].index[:5])


def validate_upload(contents: bytes, as_of: date | None) -> ValidationResult:
    errors: list[str] = []
    if type(as_of) is not date:
        errors.append("Enter the status as of date. It cannot be inferred from the file.")
    if len(contents) > MAX_UPLOAD_BYTES:
        return ValidationResult(None, errors + ["The CSV exceeds the 10 MiB prototype limit."], [])
    try:
        text = contents.decode("utf-8-sig")
        if "\x00" in text:
            return ValidationResult(None, errors + ["The CSV contains unsupported null characters."], [])
        reader = csv.reader(io.StringIO(text), strict=True)
        header = next(reader)
        if len(header) != len(set(header)):
            return ValidationResult(None, errors + ["The CSV has duplicate column headings."], [])
        for position, row in enumerate(reader, start=1):
            if row and len(row) != len(header):
                return ValidationResult(
                    None, errors + [f"Request row {position} has the wrong number of CSV fields."], []
                )
        frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except (UnicodeDecodeError, StopIteration, csv.Error, pd.errors.ParserError,
            pd.errors.EmptyDataError, ValueError) as error:
        return ValidationResult(None, errors + [f"Could not read this UTF-8 CSV: {error}"], [])

    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    extra = sorted(set(frame.columns) - set(REQUIRED_COLUMNS))
    if missing:
        errors.append("Missing required columns: " + ", ".join(missing) + ".")
    if extra:
        errors.append("Unexpected columns: " + ", ".join(extra) + ". Use only the documented synthetic schema.")
    if frame.empty:
        errors.append("The snapshot must contain at least one request.")
    # Reject schema mismatches rather than guessing column mappings.
    if missing or extra or frame.empty:
        return ValidationResult(frame, errors, [])

    frame = frame.loc[:, list(REQUIRED_COLUMNS)].copy()
    for column in frame:
        frame[column] = frame[column].fillna("").str.strip()
    for column in REQUIRED_VALUES:
        blank = frame[column].eq("")
        if blank.any():
            errors.append(f"{column} is required in request rows {_positions(blank)}.")

    duplicate = frame["PA_Request_ID"].duplicated(keep=False)
    if duplicate.any():
        errors.append(
            "PA_Request_ID must be unique within this upload. Duplicate IDs: "
            + ", ".join(frame.loc[duplicate, "PA_Request_ID"].unique()[:5]) + "."
        )
    for column, allowed in ALLOWED_VALUES.items():
        invalid = ~frame[column].isin(allowed)
        if invalid.any():
            errors.append(
                f"{column} has invalid values in request rows {_positions(invalid)}. "
                f"Allowed values: {', '.join(sorted(allowed))}."
            )

    parsed_dates: dict[str, pd.Series] = {}
    for column in ("Received_Date", "Decision_Date"):
        blank = frame[column].eq("")
        correct_format = frame[column].str.fullmatch(r"\d{4}-\d{2}-\d{2}")
        parsed = []
        for value, formatted in zip(frame[column], correct_format):
            try:
                parsed.append(date.fromisoformat(value) if formatted else None)
            except ValueError:
                parsed.append(None)
        dates = pd.Series(parsed, index=frame.index, dtype=object)
        parsed_dates[column] = dates
        reportable = pd.to_datetime(frame[column], format="%Y-%m-%d", errors="coerce")
        invalid = ~blank & (dates.isna() | reportable.isna())
        if invalid.any():
            errors.append(
                f"{column} has invalid dates in request rows {_positions(invalid)}. "
                "Use real calendar dates in YYYY-MM-DD format within Pandas' supported range."
            )
        if type(as_of) is date:
            later = dates.map(lambda value: value is not None and value > as_of)
            if later.any():
                errors.append(
                    f"{column} is after the entered status as of date in request rows "
                    f"{_positions(later)}. Check the file or the entered date."
                )
    received, decision = parsed_dates["Received_Date"], parsed_dates["Decision_Date"]
    before_received = pd.Series([
        r is not None and d is not None and d < r
        for r, d in zip(received, decision)
    ], index=frame.index)
    if before_received.any():
        errors.append(
            "Decision_Date is before Received_Date in request rows "
            + _positions(before_received) + "."
        )
    integer = frame["Resubmission_Count"].str.fullmatch(r"\d+")
    if not integer.all():
        errors.append(
            "Resubmission_Count must be a nonnegative whole number in request rows "
            + _positions(~integer) + "."
        )
    else:
        frame["Resubmission_Count"] = frame["Resubmission_Count"].str.lstrip("0").replace("", "0")
    warnings = []
    missing_decision = frame["Status"].isin(["Approved", "Denied"]) & frame["Decision_Date"].eq("")
    if missing_decision.any():
        warnings.append(
            f"{int(missing_decision.sum())} approved/denied requests have no Decision_Date. "
            "The date remains missing; it will not be inferred."
        )
    return ValidationResult(frame, errors, warnings)


def content_fingerprint(frame: pd.DataFrame) -> str:
    """Identical request contents ignore file name, row order and column order."""
    rows = frame.sort_values("PA_Request_ID").to_dict(orient="records")
    canonical = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
