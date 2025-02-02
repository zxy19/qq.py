from typing import Any, Callable, Coroutine, TYPE_CHECKING, TypeVar, Union


if TYPE_CHECKING:
    from .context import Context
    from .cog import Cog
    from .errors import CommandError

T = TypeVar('T')

Coro = Coroutine[Any, Any, T]
MaybeCoro = Union[T, Coro[T]]
CoroFunc = Callable[..., Coro[Any]]

Check = Union[Callable[["Cog", "Context[Any]"], MaybeCoro[bool]], Callable[["Context[Any]"], MaybeCoro[bool]]]
Hook = Union[Callable[["Cog", "Context[Any]"], Coro[Any]], Callable[["Context[Any]"], Coro[Any]]]
Error = Union[Callable[["Cog", "Context[Any]", "CommandError"], Coro[Any]], Callable[["Context[Any]", "CommandError"], Coro[Any]]]


# This is merely a tag type to avoid circular import issues.
# Yes, this is a terrible solution but ultimately it is the only solution.
class _BaseCommand:
    __slots__ = ()
