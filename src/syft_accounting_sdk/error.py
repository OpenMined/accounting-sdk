class ServiceException(Exception):
    """Exception raised for errors in the accounting service.

    Attributes:
        status_code: HTTP status code of the error
        body: Response body containing error details
        message: Formatted error message
    """

    def __init__(self, status_code: int, body: dict[str, str]) -> None:
        self.status_code = status_code
        self.body = body
        self.message = f"Error {status_code}: {body}"
        super().__init__(self.message) 