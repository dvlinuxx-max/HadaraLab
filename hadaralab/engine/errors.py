class MatlabError(Exception):
    """An error raised while lexing, parsing or running user code."""

    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self):
        if self.line:
            return f"Error (line {self.line}): {self.message}"
        return f"Error: {self.message}"
