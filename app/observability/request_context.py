from contextvars import ContextVar, Token

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id_ctx.get()


def set_request_id(value: str) -> Token:
    return _request_id_ctx.set(value)


def reset_request_id(token: Token) -> None:
    _request_id_ctx.reset(token)
