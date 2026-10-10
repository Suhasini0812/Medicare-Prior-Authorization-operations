"""Load the supplied request CSV and check its expected fields."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "synthetic_ma_pa_requests.csv"

REQUIRED_COLUMNS = (
    "PA_Request_ID",
    "Received_Date",
    "Procedure_Category",
    "Request_Type",
    "Status",
    "Decision_Date",
    "Documentation_Status",
    "Additional_Info_Requested",
    "Resubmission_Count",
    "Denial_Reason",
)


class MissingColumnsError(ValueError):
    """Raised when the CSV does not contain all fields used by the app."""


def load_requests(data_path: Path = DATA_FILE) -> pd.DataFrame:
    """Read the request CSV and return it after validating its columns."""
    if not data_path.is_file():
        raise FileNotFoundError(
            f"Could not find the data file at '{data_path}'. "
            "Make sure data/synthetic_ma_pa_requests.csv is in the project."
        )

    try:
        requests = pd.read_csv(data_path)
    except (pd.errors.ParserError, UnicodeDecodeError) as error:
        raise ValueError(
            f"Could not read '{data_path.name}' as a CSV file: {error}"
        ) from error

    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in requests.columns
    ]
    if missing_columns:
        missing_list = ", ".join(missing_columns)
        expected_list = ", ".join(REQUIRED_COLUMNS)
        raise MissingColumnsError(
            f"The data file is missing required column(s): {missing_list}. "
            f"Expected columns: {expected_list}."
        )

    return requests
