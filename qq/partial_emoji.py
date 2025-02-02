from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING, Type, TypeVar, Union
import re

from .asset import AssetMixin
from .error import InvalidArgument

__all__ = (
    'PartialEmoji',
)

if TYPE_CHECKING:
    from .state import ConnectionState
    from datetime import datetime
    from .types.message import PartialEmoji as PartialEmojiPayload


class _EmojiTag:
    __slots__ = ()

    id: int

    def _to_partial(self) -> PartialEmoji:
        raise NotImplementedError


PE = TypeVar('PE', bound='PartialEmoji')


class PartialEmoji(_EmojiTag, AssetMixin):
    """代表 “部分” 表情符号。
    该模型将在两种情况下给出:

    - “原始”数据事件，例如 :func:`on_raw_reaction_add`
    - 机器人无法看到的自定义表情符号，例如 :attr:`Message.reactions`

    .. container:: operations

        .. describe:: x == y

            检查两个表情符号是否相同。

        .. describe:: x != y

            检查两个表情符号是否不同。

        .. describe:: hash(x)

            返回表情符号的哈希值。

        .. describe:: str(x)

            返回为 QQ 渲染的表情符号。


    Attributes
    -----------
    custom: :class:`bool`
        表情是否是 QQ 自定义表情。
    id: :class:`int`
        自定义表情符号的 ID（如果适用）。
    """

    __slots__ = ('animated', 'name', 'id', '_state', 'custom')

    _CUSTOM_EMOJI_RE = re.compile(r'<?(?P<animated>a)?:?(?P<name>[A-Za-z0-9\_]+):(?P<id>[0-9]{13,20})>?')

    if TYPE_CHECKING:
        id: Optional[int]

    def __init__(self, *, custom: bool, id: int = None):
        self.custom = custom
        self.animated = False
        self.name = 'emoji'
        self.id = id
        self._state: Optional[ConnectionState] = None

    @classmethod
    def from_dict(cls: Type[PE], data: Union[PartialEmojiPayload, Dict[str, Any]]) -> PE:
        return cls(
            id=int(data.get('id')),
            custom=True if data.get('type') == 1 else 0,
        )

    @classmethod
    def from_str(cls: Type[PE], value: str) -> PE:
        """将表情符号的 QQ 字符串表示形式转换为 :class:`PartialEmoji`。
        接受的格式是：

        - ``a:name:id``
        - ``<a:name:id>``
        - ``name:id``
        - ``<:name:id>``

        如果格式不匹配，则假定它是一个 unicode 表情符号。

        Parameters
        ------------
        value: :class:`str`
            表情符号的字符串表示。

        Returns
        --------
        :class:`PartialEmoji`
            此字符串中的表情符号。
        """
        match = cls._CUSTOM_EMOJI_RE.match(value)
        if match is not None:
            groups = match.groupdict()
            emoji_id = int(groups['id'])
            return cls(id=emoji_id, custom=True)

        return cls(id=value, custom=False)

    def to_dict(self) -> Dict[str, Any]:
        o: Dict[str, Any] = {'id': self.id, 'type': '1' if self.custom else '2'}
        return o

    def _to_partial(self) -> PartialEmoji:
        return self

    @classmethod
    def with_state(
            cls: Type[PE], state: ConnectionState, *, custom: bool, id: int = None
    ) -> PE:
        self = cls(custom=custom, id=id)
        self._state = state
        return self

    def __str__(self) -> str:
        if self.id is None:
            return self.name
        if self.animated:
            return f'<a:{self.name}:{self.id}>'
        return f'<{self.name}:{self.id}>'

    def __repr__(self):
        return f'<{self.__class__.__name__} id={self.id} type={"1" if self.custom else "2"}>'

    def __eq__(self, other: Any) -> bool:
        if self.is_unicode_emoji():
            return isinstance(other, PartialEmoji) and self.name == other.name

        if isinstance(other, _EmojiTag):
            return self.id == other.id
        return False

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash((self.id, self.name))

    def is_custom_emoji(self) -> bool:
        """:class:`bool`: 检查这是否是自定义的非 Unicode 表情符号。"""
        return self.custom

    def is_unicode_emoji(self) -> bool:
        """:class:`bool`: 检查这是否是 Unicode 表情符号。"""
        return not self.custom

    def _as_reaction(self) -> str:
        if self.id is None:
            return self.name
        return f'{self.name}:{self.id}'

    async def read(self) -> bytes:
        if self.is_unicode_emoji():
            raise InvalidArgument('PartialEmoji 不是自定义表情符号')

        return await super().read()
