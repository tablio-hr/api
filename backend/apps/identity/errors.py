class CommandDenied(Exception):
    def __init__(self, status: int = 403, code: str = "forbidden", detail: str = "Forbidden."):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.response_body = {"detail": detail, "code": code}


class LastAdminDenied(CommandDenied):
    def __init__(self):
        super().__init__(403, "last_admin", "Forbidden.")


class StrongerRoleDenied(CommandDenied):
    def __init__(self):
        super().__init__(403, "forbidden", "Forbidden.")


class ConflictDenied(CommandDenied):
    def __init__(self, code: str = "conflict", detail: str = "Conflict."):
        super().__init__(409, code, detail)


class NotFoundDenied(CommandDenied):
    def __init__(self):
        super().__init__(404, "not_found", "Not found.")
