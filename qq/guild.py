from __future__ import annotations

from typing import (
    Dict,
    List,
    Union,
    Optional,
    Tuple,
    TYPE_CHECKING,
    Any,
    Sequence,
    overload,
)

from . import utils, abc
from .role import Role
from .member import Member
from .error import InvalidData
from .colour import Colour
from .error import InvalidArgument, ClientException
from .channel import *
from .channel import _guild_channel_factory, _channel_factory
from .mixins import Hashable
from .user import User
from .iterators import MemberIterator
from .asset import Asset
from .file import File


MISSING = utils.MISSING

if TYPE_CHECKING:
    from .state import ConnectionState
    from .types.guild import Guild as GuildPayload
    from .channel import TextChannel, CategoryChannel, AppChannel, LiveChannel, ThreadChannel
    from .state import ConnectionState

    GuildChannel = Union[VoiceChannel, TextChannel, CategoryChannel, AppChannel, LiveChannel, ThreadChannel]
    VocalGuildChannel = Union[VoiceChannel]
    ByCategoryItem = Tuple[Optional[CategoryChannel], List[GuildChannel]]


class Guild(Hashable):
    """代表一个 QQ guild.
    这在官方 QQ UI 中称为 “频道” 。

    .. container:: operations

        .. describe:: x == y
            检查两个 guild 是否相等。
        .. describe:: x != y
            检查两个 guild 是否不相等。
        .. describe:: hash(x)
            返回 guild 的哈希值。
        .. describe:: str(x)
            返回 guild 的名称。

    Attributes
    ----------
    name: :class:`str`
        guild 名称。
    id: :class:`int`
        guild 的 ID。
    owner_id: :class:`int`
        guild 所有者的ID。使用 :attr:`Guild.owner` 代替。
    unavailable: :class:`bool`
        指示频道是否不可用。如果这是 ``True`` 则 :attr:`Guild.id` 之外的其他属性的可靠性很小，它们可能都是 ``None``。
        如果频道不可用，最好不要对频道做任何事情。
    max_members: Optional[:class:`int`]
        guild 成员的最大数量。

        .. note::

            该属性只能通过 :meth:`.Client.fetch_guild` 获得。

    description: Optional[:class:`str`]
        guild 的说明。
    """

    __slots__ = (
        'id',
        'name',
        'icon',
        'owner_id',
        '_member_count',
        'max_members',
        'description',
        'joined_at',
        '_channels',
        '_members',
        '_roles',
        '_state',
        '_large',
        'unavailable'
    )

    def __init__(self, data: GuildPayload, state: ConnectionState):
        self._channels: Dict[int, GuildChannel] = {}
        self._members: Dict[int, Member] = {}
        self._state: ConnectionState = state
        self._from_data(data)

    def _add_role(self, role: Role, /) -> None:
        self._roles[role.id] = role

    def _remove_role(self, role_id: int, /) -> Role:
        # this raises KeyError if it fails.
        role = self._roles.pop(role_id)
        return role

    def _from_data(self, guild: GuildPayload) -> None:
        self.id = int(guild.get('id'))
        self.name = guild.get('name')
        self.icon = guild.get('icon')
        self.owner_id = guild.get('owner_id')
        if self.owner_id:
            self.owner_id = int(self.owner_id)
        self._member_count = guild.get('member_count')
        self.max_members = guild.get('max_members')
        self.description = guild.get('description')
        self.joined_at = guild.get('joined_at')
        self.unavailable: bool = guild.get('unavailable', False)
        self._roles: Dict[int, Role] = {}
        state = self._state  # speed up attribute access
        self._large: Optional[bool] = None if self._member_count is None else self._member_count >= 250
        for r in guild.get('roles', []):
            role = Role(guild=self, data=r, state=state)
            self._roles[role.id] = role
        self._sync()

    def _add_channel(self, channel: GuildChannel, /) -> None:
        self._channels[channel.id] = channel

    def _remove_channel(self, channel: GuildChannel, /) -> None:
        self._channels.pop(channel.id, None)

    def __str__(self) -> str:
        return self.name or ''

    def __repr__(self) -> str:
        attrs = (
            ('id', self.id),
            ('name', self.name),
            ('member_count', getattr(self, '_member_count', None)),
        )
        inner = ' '.join('%s=%r' % t for t in attrs)
        return f'<Guild {inner}>'

    def _sync(self) -> None:
        # I know it's jank to put a sync requests here,
        # but QQ just does not give all the info about guilds unless you requests it
        channels, roles, members = self._state.http.sync_guild_channels_roles(self.id)
        if members:
            for mdata in members:
                member = Member(data=mdata, guild=self, state=self._state)
                self._add_member(member)
        else:
            member = Member(data=self._state.http.sync_get_bot_member(self.id, self._state.user.id),
                            guild=self, state=self._state)
            self._add_member(member)
        if 'roles' in roles:
            for r in roles['roles']:
                role = Role(guild=self, data=r, state=self._state)
                self._roles[role.id] = role
        for c in channels:
            factory, ch_type = _guild_channel_factory(c['type'])
            if factory:
                self._add_channel(factory(guild=self, data=c, state=self._state))  # type: ignore

    @property
    def channels(self) -> List[GuildChannel]:
        """List[:class:`abc.GuildChannel`]: 属于该频道的子频道列表。"""
        return list(self._channels.values())

    @property
    def shard_id(self) -> int:
        """:class:`int`: 如果适用，返回此频道的分片 ID。"""
        count = self._state.shard_count
        if count is None:
            return 0
        return (self.id >> 22) % count

    @property
    def owner(self) -> Optional[Member]:
        """Optional[:class:`Member`]: 拥有频道的成员。"""
        return self.get_member(self.owner_id)

    @property
    def members(self) -> List[Member]:
        """List[:class:`Member`]: 属于该频道的成员列表。"""
        return list(self._members.values())

    def get_role(self, role_id: int, /) -> Optional[Role]:
        """返回具有给定 ID 的 Role。

        Parameters
        -----------
        role_id: :class:`int`
            要搜索的 ID。

        Returns
        --------
        Optional[:class:`Role`]
            Role 或如果未找到，则 “None”。
        """
        return self._roles.get(role_id)

    @property
    def large(self) -> bool:
        """:class:`bool`: 指示频道是否是“大型”频道。

        一个大型频道被定义为拥有超过 ``large_threshold`` 计数成员，对于这个库，它被设置为 250。
        """
        if self._large is None:
            try:
                return self._member_count >= 250
            except AttributeError:
                return len(self._members) >= 250
        return self._large

    @property
    def me(self) -> Member:
        """:class:`Member`: 类似于 :attr:`Client.user` ，除了它是 :class:`Member` 的一个实例。
        这主要用于获取您自己的 Member 版本。
        """
        self_id = self._state.user.id
        # The self member is *always* cached
        return self.get_member(self_id)  # type: ignore

    @property
    def text_channels(self) -> List[TextChannel]:
        """List[:class:`TextChannel`]: 属于该频道的文本频道列表。这是按位置排序的，从上到下按 UI 顺序排列。
        """
        r = [ch for ch in self._channels.values() if isinstance(ch, TextChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    @property
    def categories(self) -> List[CategoryChannel]:
        """List[:class:`CategoryChannel`]: 属于该频道的类别列表。这是按位置排序的，从上到下按 UI 顺序排列。
        """
        r = [ch for ch in self._channels.values() if isinstance(ch, CategoryChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    def by_category(self) -> List[ByCategoryItem]:
        """返回每个 :class:`CategoryChannel` 及其关联的频道。
        这些频道和类别按官方 QQ UI 顺序排序。
        如果频道没有类别，则元组的第一个元素是 “None”。

        Returns
        --------
        List[Tuple[Optional[:class:`CategoryChannel`], List[:class:`abc.GuildChannel`]]]:
            类别及其关联的频道。
        """
        grouped: Dict[Optional[int], List[GuildChannel]] = {}
        for channel in self._channels.values():
            if isinstance(channel, CategoryChannel):
                grouped.setdefault(channel.id, [])
                continue

            try:
                grouped[channel.category_id].append(channel)
            except KeyError:
                grouped[channel.category_id] = [channel]

        def key(t: ByCategoryItem) -> Tuple[Tuple[int, int], List[GuildChannel]]:
            k, v = t
            return (k.position, k.id) if k else (-1, -1), v

        _get = self._channels.get
        as_list: List[ByCategoryItem] = [(_get(k), v) for k, v in grouped.items()]  # type: ignore
        as_list.sort(key=key)
        for _, channels in as_list:
            channels.sort(key=lambda c: (c._sorting_bucket, c.position, c.id))
        return as_list

    def _resolve_channel(self, id: Optional[int], /) -> Optional[Union[GuildChannel,]]:
        if id is None:
            return

        return self._channels.get(id)

    def get_channel(self, channel_id: int, /) -> Optional[GuildChannel]:
        """返回具有给定 ID 的频道。

        Parameters
        -----------
        channel_id: :class:`int`
            要搜索的 ID。

        Returns
        --------
        Optional[:class:`.abc.GuildChannel`]
            返回的频道或 “None”（如果未找到）。
        """
        return self._channels.get(channel_id)

    def get_member(self, user_id: int, /) -> Optional[Member]:
        """返回具有给定 ID 的成员。

        Parameters
        -----------
        user_id: :class:`int`
            要搜索的 ID。

        Returns
        --------
        Optional[:class:`Member`]
            返回成员或如果未找到 “None” 。
        """
        return self._members.get(user_id)

    @property
    def roles(self) -> List[Role]:
        """List[:class:`Role`]: 以层级顺序返回频道身份组的 :class:`list`。此列表的第一个元素将是层次结构中的最低身份组。
        """
        return sorted(self._roles.values())

    def _add_member(self, member: Member, /) -> None:
        self._members[member.id] = member

    @property
    def chunked(self) -> bool:
        count = getattr(self, '_member_count', None)
        if count is None:
            return False
        return count == len(self._members)

    def get_member_named(self, name: str, /) -> Optional[Member]:
        """返回找到的第一个与提供的名称匹配的成员。
        如果传递了昵称，则通过昵称查找它。
        如果没有找到成员，则返回 “None”。

        Parameters
        -----------
        name: :class:`str`
            要查找的成员的名称。

        Returns
        --------
        Optional[:class:`Member`]
            此频道中具有关联名称的成员。如果未找到，则返回 “None”。
        """
        members = self.members
        result = utils.get(members, name=name[:-5])
        if result is not None:
            return result

        def pred(m: Member) -> bool:
            return m.nick == name or m.name == name

        return utils.find(pred, members)

    @property
    def member_count(self) -> int:
        """:class:`int`: 无论是否完全加载，都返回真实的成员计数。

        .. warning::

            由于 QQ 的限制，为了使该属性保持最新和准确，它需要指定 :attr:`Intents.members` 。
        """
        return self._member_count

    async def create_text_channel(
            self,
            name: str,
            *,
            reason: Optional[str] = None,
            category: Optional[CategoryChannel] = None,
            position: int = MISSING,
    ) -> TextChannel:
        """|coro|
        为频道创建一个 :class:`TextChannel` 。

        .. note::

            创建指定位置的频道不会更新其他频道的位置以效仿。需要对 :meth:`~TextChannel.edit` 进行后续调用以更新频道在频道列表中的位置。

        Examples
        ----------
        创建基本频道：

        .. code-block:: python3

            channel = await guild.create_text_channel('cool-channel')

        Parameters
        -----------
        name: :class:`str`
            频道的名称。
        category: Optional[:class:`CategoryChannel`]
            将新创建的子频道置于其下的类别。
        position: :class:`int`
            在子频道列表中的位置。这是一个从 0 开始的数字。例如顶部子频道是位置 0。
        reason: Optional[:class:`str`]
            创建此频道的原因。

        Raises
        -------
        Forbidden
            您没有创建此频道的适当权限。
        HTTPException
            创建频道失败。
        Returns
        -------
        :class:`TextChannel`
            刚刚创建的频道。
        """

        options = {}
        if position is not MISSING:
            options['position'] = position

        data = await self._create_channel(
            name, channel_type=ChannelType.text, category=category, reason=reason, **options
        )
        channel = TextChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    def _create_channel(
        self,
        name: str,
        channel_type: ChannelType,
        category: Optional[CategoryChannel] = None,
        **options: Any,
    ):
        parent_id = category.id if category else None
        return self._state.http.create_channel(
            self.id, channel_type.value, name=name, parent_id=parent_id, **options
        )

    async def create_live_channel(
        self,
        name: str,
        *,
        position: int = MISSING,
        category: Optional[CategoryChannel] = None,
        reason: Optional[str] = None,
    ) -> LiveChannel:
        """|coro|
        这类似于 :meth:`create_live_channel` ，除了创建一个 :class:`LiveChannel` 。

        Parameters
        -----------
        name: :class:`str`
            频道的名称。
        category: Optional[:class:`LiveChannel`]
            将新创建的频道置于其下的类别。
        position: :class:`int`
            在频道列表中的位置。这是一个从 0 开始的数字。例如顶部通道是位置 0。
        reason: Optional[:class:`str`]
            创建此频道的原因。

        Raises
        ------
        Forbidden
            您没有创建此频道的适当权限。
        HTTPException
            创建频道失败。

        Returns
        -------
        :class:`LiveChannel`
            刚刚创建的频道。
        """

        options: Dict[str, Any] = {}
        if position is not MISSING:
            options['position'] = position

        data = await self._create_channel(
            name, channel_type=ChannelType.live, category=category, reason=reason, **options
        )
        channel = LiveChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    async def create_app_channel(
        self,
        name: str,
        *,
        position: int = MISSING,
        category: Optional[CategoryChannel] = None,
        reason: Optional[str] = None,
    ) -> AppChannel:
        """|coro|
        这类似于 :meth:`create_app_channel` ，除了生成一个 :class:`AppChannel`。

        Parameters
        -----------
        name: :class:`str`
            频道的名称。
        category: Optional[:class:`AppChannel`]
            将新创建的频道置于其下的类别。
        position: :class:`int`
            在频道列表中的位置。这是一个从 0 开始的数字。例如顶部通道是位置 0。
        reason: Optional[:class:`str`]
            创建此频道的原因。

        Raises
        ------
        Forbidden
            您没有创建此频道的适当权限。
        HTTPException
            创建频道失败。

        Returns
        -------
        :class:`AppChannel`
            刚刚创建的频道。
        """

        options: Dict[str, Any] = {}
        if position is not MISSING:
            options['position'] = position

        data = await self._create_channel(
            name, channel_type=ChannelType.live, category=category, reason=reason, **options
        )
        channel = AppChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    async def create_thread_channel(
        self,
        name: str,
        *,
        position: int = MISSING,
        category: Optional[CategoryChannel] = None,
        reason: Optional[str] = None,
    ) -> ThreadChannel:
        """|coro|
        这类似于 :meth:`create_thread_channel` ，除了生成一个 :class:`ThreadChannel`。

        Parameters
        -----------
        name: :class:`str`
            频道的名称。
        category: Optional[:class:`ThreadChannel`]
            将新创建的频道置于其下的类别。
        position: :class:`int`
            在频道列表中的位置。这是一个从 0 开始的数字。例如顶部通道是位置 0。
        reason: Optional[:class:`str`]
            创建此频道的原因。

        Raises
        ------
        Forbidden
            您没有创建此频道的适当权限。
        HTTPException
            创建频道失败。

        Returns
        -------
        :class:`LiveChannel`
            刚刚创建的频道。
        """

        options: Dict[str, Any] = {}
        if position is not MISSING:
            options['position'] = position

        data = await self._create_channel(
            name, channel_type=ChannelType.live, category=category, reason=reason, **options
        )
        channel = ThreadChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    async def create_category(
        self,
        name: str,
        *,
        reason: Optional[str] = None,
        position: int = MISSING,
    ) -> CategoryChannel:
        """|coro|
        与 :meth:`create_text_channel` 相同，除了创建一个 :class:`CategoryChannel`。

        .. note::
            此函数不支持 ``category`` 参数，因为类别不能有类别。

        Raises
        ------
        Forbidden
            您没有创建此频道的适当权限。
        HTTPException
            创建频道失败。

        Returns
        -------
        :class:`CategoryChannel`
            刚刚创建的频道。
        """
        options: Dict[str, Any] = {}
        if position is not MISSING:
            options['position'] = position

        data = await self._create_channel(
            name, channel_type=ChannelType.category, reason=reason, **options
        )
        channel = CategoryChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    create_category_channel = create_category

    async def fetch_channels(self) -> Sequence[GuildChannel]:
        """|coro|
        检索频道拥有的所有 :class:`abc.GuildChannel`。

        .. note::
            该方法是一个 API 调用。 对于一般用途，请考虑 :attr:`channels`。

        Raises
        -------
        InvalidData
            从 QQ 接收到未知的频道类型。
        HTTPException
            检索频道失败。

        Returns
        -------
        Sequence[:class:`abc.GuildChannel`]
            频道内的所有频道。
        """
        data = await self._state.http.get_all_guild_channels(self.id)

        def convert(d):
            factory, ch_type = _guild_channel_factory(d['type'])
            if factory is None:
                raise InvalidData('Unknown channel type {type} for channel ID {id}.'.format_map(d))

            channel = factory(guild=self, state=self._state, data=d)
            return channel

        return [convert(d) for d in data]

    def fetch_members(self, *, limit: int = 1000) -> MemberIterator:
        """检索一个 :class:`.AsyncIterator` 来接收频道的成员。为了使用它，必须启用:meth:`Intents.members`。

        .. note::
            该方法是一个 API 调用。对于一般用法，请考虑 :attr:`members`。

        Parameters
        ----------
        limit: Optional[:class:`int`]
            要检索的成员数。默认为 1000。传递“无”以获取所有成员。请注意，这可能很慢。

        Raises
        ------
        ClientException
            成员意图未启用。
        HTTPException
            获取成员失败。

        Yields
        ------
        :class:`.Member`
            已解析成员数据的成员。

        Examples
        --------
        用法  ::

            async for member in guild.fetch_members(limit=150):
                print(member.name)

        展平成一个列表 ::

            members = await guild.fetch_members(limit=150).flatten()
            # 成员现在是一个Member列表 ...

        """

        if not self._state._intents.members:
            raise ClientException('Intents.members must be enabled to use this.')

        return MemberIterator(self, limit=limit)

    async def fetch_member(self, member_id: int, /) -> Member:
        """|coro|
        从频道 ID 和成员 ID 中检索:class:`Member`。

        .. note::
            该方法是一个 API 调用。如果您启用了 :attr:`Intents.members` 和成员缓存，请考虑使用 :meth:`get_member`。

        Parameters
        -----------
        member_id: :class:`int`
            要从中获取的成员 ID。

        Raises
        -------
        Forbidden
            您无权访问频道。
        HTTPException
            获取成员失败。

        Returns
        --------
        :class:`Member`
            来自会员 ID 的会员。
        """
        data = await self._state.http.get_member(self.id, member_id)
        return Member(data=data, state=self._state, guild=self)

    async def fetch_channel(self, channel_id: int, /) -> GuildChannel:
        """|coro|
        检索具有指定 ID 的 :class:`.abc.GuildChannel`。

        .. note::

            该方法是一个 API 调用。对于一般用法，请考虑 :meth:`get_channel`。

        Raises
        -------
        :exc:`.InvalidData`
            从 QQ 接收到未知的频道类型或频道所属的频道与此对象中指向的频道不同。
        :exc:`.HTTPException`
            检索频道失败。
        :exc:`.NotFound`
            无效的频道 ID。
        :exc:`.Forbidden`
            您无权获取此频道。

        Returns
        --------
        :class:`.abc.GuildChannel`
            来自 ID 的频道。
        """
        data = await self._state.http.get_channel(channel_id)

        factory, ch_type = _channel_factory(data['type'])
        if factory is None:
            raise InvalidData('Unknown channel type {type} for channel ID {id}.'.format_map(data))

        guild_id = int(data['guild_id'])
        if self.id != guild_id:
            raise InvalidData('Guild ID resolved to a different guild')

        channel: GuildChannel = factory(guild=self, state=self._state, data=data)  # type: ignore
        return channel

    async def fetch_roles(self) -> List[Role]:
        """|coro|
        检索频道拥有的所有 :class:`Role`。
        .. note::

            该方法是一个 API 调用。对于一般用法，请考虑 :attr:`roles`。
        .. versionadded:: 1.3

        Raises
        -------
        HTTPException
            检索身份组失败。

        Returns
        -------
        List[:class:`Role`]
            频道中的所有身份组。
        """
        data = await self._state.http.get_roles(self.id)
        return [Role(guild=self, state=self._state, data=d) for d in data]

    @overload
    async def create_role(
        self,
        *,
        reason: Optional[str] = ...,
        name: str = ...,
        colour: Union[Colour, int] = ...,
        hoist: bool = ...,
        mentionable: bool = ...,
    ) -> Role:
        ...

    @overload
    async def create_role(
        self,
        *,
        reason: Optional[str] = ...,
        name: str = ...,
        color: Union[Colour, int] = ...,
        hoist: bool = ...,
        mentionable: bool = ...,
    ) -> Role:
        ...

    async def create_role(
        self,
        *,
        name: str = MISSING,
        color: Union[Colour, int] = MISSING,
        colour: Union[Colour, int] = MISSING,
        hoist: bool = MISSING,
        mentionable: bool = MISSING,
        reason: Optional[str] = None,
    ) -> Role:
        """|coro|
        为频道创建一个身份组。
        
        Parameters
        -----------
        name: :class:`str`
            身份组名称。
        colour: Union[:class:`Colour`, :class:`int`]
            身份组的颜色。默认为 :meth:`Colour.default` 。这也是 ``Color`` 的别名。
        hoist: :class:`bool`
            指示身份组是否应单独显示在成员列表中。默认为 ``False``。
        mentionable: :class:`bool`
            指示身份组是否应该被其他人提及。默认为 ``False``。
        reason: Optional[:class:`str`]
            创建此身份组的原因。
            
        Raises
        -------
        Forbidden
            您无权创建该身份组。
        HTTPException
            创建身份组失败。
        InvalidArgument
            给出了无效的关键字参数。
            
        Returns
        --------
        :class:`Role`
            新创建的身份组。
        """
        fields: Dict[str, Any] = {}

        actual_colour = colour or color or Colour.default()
        if isinstance(actual_colour, int):
            fields['color'] = actual_colour
        else:
            fields['color'] = actual_colour.value

        if hoist is not MISSING:
            fields['hoist'] = hoist

        if mentionable is not MISSING:
            fields['mentionable'] = mentionable

        if name is not MISSING:
            fields['name'] = name

        data = await self._state.http.create_role(self.id, reason=reason, **fields)
        role = Role(guild=self, data=data, state=self._state)
        
        return role

    async def kick(self, user: Member, *, reason: Optional[str] = None) -> None:
        """|coro|
        将一个用户踢出公会。

        Parameters
        -----------
        user: :class:`Member`
            踢出的用户。
        reason: Optional[:class:`str`]
            用户被踢的原因。

        Raises
        -------
        Forbidden
            您没有正确的踢出权限。
        HTTPException
            踢出失败。
        """
        await self._state.http.kick(user.id, self.id, reason=reason)


