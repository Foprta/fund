from integrations.sheets_public import SheetsPublicClient


def get_sheets_client() -> SheetsPublicClient:
    return SheetsPublicClient()
