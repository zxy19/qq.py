from __future__ import annotations
from typing import Any, Dict, List, Optional, TypeVar, Union, overload, TYPE_CHECKING

from .colour import Colour
from .mixins import Hashable
from .utils import MISSING

__all__ = (
    'Role',
)

if TYPE_CHECKING:
    from .types.role import (
        Role as RolePayload,
    )
    from .guild import Guild
    from .member import Member
    from .state import ConnectionState

R = TypeVar('R', bound='Role')


class Role(Hashable):
    """代表 :class:`Guild` 中的 QQ 身份组。

    .. container:: operations

        .. describe:: x == y

            检查两个身份组是否相等。

        .. describe:: x != y

            检查两个身份组是否不相等。

        .. describe:: hash(x)

            返回身份组的哈希值。

        .. describe:: str(x)

            返回身份组的名称。

    Attributes
    ----------
    id: :class:`int`
        身份组的 ID。
    name: :class:`str`
        身份组名称。
    guild: :class:`Guild`
        身份组所属的公会。
    hoist: :class:`bool`
         指示身份组是否将与其他成员分开显示。
    """
    __slots__ = (
        'id',
        'name',
        '_colour',
        'hoist',
        'guild',
        '_state',
    )

    def __init__(self, *, guild: Guild, state: ConnectionState, data: RolePayload):
        self.guild: Guild = guild
        self._state: ConnectionState = state
        self.id: int = int(data['id'])
        self._update(data)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'<Role id={self.id} name={self.name!r}>'

    def __lt__(self: R, other: R) -> bool:
        if not isinstance(other, Role) or not isinstance(self, Role):
            return NotImplemented

        if self.guild != other.guild:
            raise RuntimeError('cannot compare roles from two different guilds.')

        # the @everyone role is always the lowest role in hierarchy
        guild_id = self.guild.id
        if self.id == guild_id:
            # everyone_role < everyone_role -> False
            return other.id != guild_id

        if self.id < other.id:
            return True

        if self.id == other.id:
            return int(self.id) > int(other.id)

        return False

    def __le__(self: R, other: R) -> bool:
        r = Role.__lt__(other, self)
        if r is NotImplemented:
            return NotImplemented
        return not r

    def __gt__(self: R, other: R) -> bool:
        return Role.__lt__(other, self)

    def __ge__(self: R, other: R) -> bool:
        r = Role.__lt__(self, other)
        if r is NotImplemented:
            return NotImplemented
        return not r

    def _update(self, data: RolePayload):
        self.name: str = data['name']
        self._colour: int = data.get('color', 0)
        self.hoist: bool = data.get('hoist', False)

    def is_default(self) -> bool:
        """:class:`bool`: 检查身份组是否为默认身份组。"""
        return self.guild.id == self.id

    @property
    def colour(self) -> Colour:
        """:class:`Colour`: 返回身份组颜色。 存在 ``color`` 别名。"""
        return Colour(self._colour)

    @property
    def color(self) -> Colour:
        """:class:`Colour`: 返回身份组颜色。 存在 ``color`` 别名。"""
        return self.colour

    @property
    def mention(self) -> str:
        """:class:`str`: 返回允许你提及身份组的字符串。"""
        return f'<@&{self.id}>'

    @property
    def members(self) -> List[Member]:
        """List[:class:`Member`]: 返回具有此身份组的所有成员。"""
        all_members = self.guild.members
        if self.is_default():
            return all_members

        role_id = self.id
        return [member for member in all_members if member._roles.has(role_id)]

    async def edit(
            self,
            *,
            name: str = MISSING,
            colour: Union[Colour, int] = MISSING,
            color: Union[Colour, int] = MISSING,
            hoist: bool = MISSING,
            reason: Optional[str] = MISSING,
    ) -> Optional[Role]:

        payload: Dict[str, Any] = {'info': {}, 'filter': {
            k: 0 for k in ['color', 'name', 'hoist']
        }}
        if color is not MISSING:
            colour = color

        if colour is not MISSING:
            if isinstance(colour, int):
                payload['info']['color'] = colour
            else:
                payload['info']['color'] = colour.value
            payload['filter']['color'] = 1

        if name is not MISSING:
            payload['info']['name'] = name
            payload['filter']['name'] = 1

        if hoist is not MISSING:
            payload['info']['hoist'] = hoist
            payload['filter']['hoist'] = 1

        data = await self._state.http.edit_role(self.guild.id, self.id, reason=reason, **payload)
        return Role(guild=self.guild, data=data, state=self._state)

    async def delete(self, *, reason: Optional[str] = None) -> None:
        """|coro|
        删除身份组。
        
        Parameters
        -----------
        reason: Optional[:class:`str`]
            删除该身份组的原因。
            
        Raises
        --------
        Forbidden
            你无权删除该身份组。
        HTTPException
            删除身份组失败。
        """

        await self._state.http.delete_role(self.guild.id, self.id, reason=reason)
