from __future__ import annotations

import asyncio
import copy
from datetime import datetime
from typing import overload, Optional, Union, List, TYPE_CHECKING, TypeVar, Dict, Any

from .asset import Asset
from .enum import ChannelType
from .error import InvalidArgument
from .mention import AllowedMentions
from .utils import MISSING

if TYPE_CHECKING:
    from .member import Member
    from .channel import CategoryChannel, TextChannel, PartialMessageable
    from .guild import Guild
    from .state import ConnectionState
    from .message import Message, MessageReference, PartialMessage
    from .types.channel import (
        Channel as ChannelPayload,
    )

    PartialMessageableChannel = Union[TextChannel, PartialMessageable]
    MessageableChannel = Union[PartialMessageableChannel]

__all__ = ('Messageable',
           'GuildChannel')


class _Undefined:
    def __repr__(self) -> str:
        return 'see-below'


_undefined: Any = _Undefined()


class Messageable:
    """一个 记录了可以发送消息的模型上的常见操作的ABC。

    以下实现了这个 ABC：

    - :class:`~qq.TextChannel`
    - :class:`~qq.User`
    - :class:`~qq.Member`
    - :class:`~qq.ext.commands.Context`

    """

    __slots__ = ()
    _state: ConnectionState

    async def _get_channel(self) -> MessageableChannel:
        raise NotImplementedError

    @overload
    async def send(
            self,
            content: Optional[str] = ...,
            *,
            tts: bool = ...,
            image: str = ...,
            reference: Union[Message, MessageReference, PartialMessage] = ...,
            mention_author: Member = ...,
    ) -> Message:
        ...

    async def send(
            self,
            content=None,
            *,
            image=None,
            reference=None,
            mention_author=None,
            ark=None,
    ):
        """|coro|
        使用给定的内容向目的地发送消息。
        content 必须是可以通过 ``str(content)`` 转换为字符串的类型。
        如果是主动信息，不一定会有返回。

        Parameters
        ------------
        content: Optional[:class:`str`]
            发送的信息内容。
        image: :class:`str`
            要发送的图片链接
        ark: Optional[:class:'qq.Ark']
            要发送的 Ark 类
        reference: Union[:class:`~qq.Message`, :class:`~qq.MessageReference`, :class:`~qq.PartialMessage`]
            对您正在回复的 :class:`~qq.Message` 的引用，可以使用 :meth:`~qq.Message.to_reference` 创建或直接作为 :class:`~qq.Message` 传递。
        mention_author: Optional[:class:`Member`]
            如果设置了，将会在消息前面提及该用户。


        Raises
        --------
        ~qq.HTTPException
            发送信息失败。
        ~qq.Forbidden
            您没有发送消息的适当权限。
        ~qq.InvalidArgument
            ``reference`` 不是 :class:`~qq.Message` 、
            :class:`~qq.MessageReference` 或 :class:`~qq.PartialMessage` 。

        Returns
        ---------
        :class:`~qq.Message`
            发送的消息。
        """

        channel = await self._get_channel()
        state = self._state
        content = str(content) if content is not None else None

        if mention_author is not None:
            content = mention_author.mention + content

        if reference is not None:
            try:
                reference = reference.to_message_reference_dict()
            except AttributeError:
                raise InvalidArgument(
                    '参考参数必须是 Message、 MessageReference 或 PartialMessage') from None

        data = await state.http.send_message(
            channel.id,
            content,
            ark=ark,
            message_reference=reference,
            image_url=image
        )

        if 'code' in data:
            return None

        ret = state.create_message(channel=channel, data=data)
        return ret

    async def fetch_message(self, id: int, /) -> Message:
        """|coro|
        从目的地检索单个 :class:`~qq.Message`。

        Parameters
        ------------
        id: :class:`int`
            要查找的消息 ID。

        Raises
        --------
        ~qq.NotFound
            未找到指定的消息。
        ~qq.Forbidden
            您没有获取消息所需的权限。
        ~qq.HTTPException
            检索消息失败。

        Returns
        --------
        :class:`~qq.Message`
            消息要求。
        """
        id = id
        channel = await self._get_channel()
        data = await self._state.http.get_message(channel.id, id)
        return self._state.create_message(channel=channel, data=data)


GCH = TypeVar('GCH', bound='GuildChannel')


class GuildChannel:
    """详细介绍 QQ 子频道上常见操作的 ABC。

    以下实现了这个 ABC：

    - :class:`~qq.TextChannel`
    - :class:`~qq.VoiceChannel`
    - :class:`~qq.CategoryChannel`
    - :class:`~qq.ThreadChannel`
    - :class:`~qq.LiveChannel`
    - :class:`~qq.AppChannel`

    Attributes
    -----------
    name: :class:`str`
        子频道名称。
    guild: :class:`~qq.Guild`
        子频道所属的频道。
    position: :class:`int`
        在频道列表中的位置。这是一个从 0 开始的数字。例如顶部子是位置 0。
    """

    __slots__ = ()

    id: int
    name: str
    guild: Guild
    type: ChannelType
    position: int
    category_id: Optional[int]
    _state: ConnectionState

    if TYPE_CHECKING:
        def __init__(self, *, state: ConnectionState, guild: Guild, data: Dict[str, Any]):
            ...

    def __str__(self) -> str:
        return self.name

    @property
    def _sorting_bucket(self) -> int:
        raise NotImplementedError

    def _update(self, guild: Guild, data: Dict[str, Any]) -> None:
        raise NotImplementedError

    async def _move(
            self,
            position: int,
            parent_id: Optional[Any] = None,
            *,
            reason: Optional[str],
    ) -> None:
        if position < 0:
            raise InvalidArgument('频道位置不能小于 0。')

        http = self._state.http
        bucket = self._sorting_bucket
        channels: List[GuildChannel] = [c for c in self.guild.channels if c._sorting_bucket == bucket]

        channels.sort(key=lambda c: c.position)

        try:
            # remove ourselves from the channel list
            channels.remove(self)
        except ValueError:
            # not there somehow lol
            return
        else:
            index = next((i for i, c in enumerate(channels) if c.position >= position), len(channels))
            # add ourselves at our designated position
            channels.insert(index, self)

        payload = []
        for index, c in enumerate(channels):
            d: Dict[str, Any] = {'id': c.id, 'position': index}
            if parent_id is not _undefined and c.id == self.id:
                d.update(parent_id=parent_id)
            payload.append(d)

        await asyncio.gather(*http.bulk_channel_update(self.guild.id, payload, reason=reason))

    async def _edit(self, options: Dict[str, Any], reason: Optional[str]) -> Optional[ChannelPayload]:
        try:
            parent = options.pop('category')
        except KeyError:
            parent_id = _undefined
        else:
            parent_id = parent and parent.id

        try:
            position = options.pop('position')
        except KeyError:
            if parent_id is not _undefined:
                options['parent_id'] = parent_id
        else:
            await self._move(position, parent_id=parent_id, reason=reason)

        try:
            ch_type = options['type']
        except KeyError:
            pass
        else:
            if not isinstance(ch_type, ChannelType):
                raise InvalidArgument('type 字段必须是 ChannelType 类型')
            options['type'] = ch_type.value

        if options:
            return await self._state.http.edit_channel(self.id, reason=reason, **options)

    @property
    def mention(self) -> str:
        """:class:`str`: 允许您提及频道的字符串。"""
        return f'<#{self.id}>'

    @property
    def category(self) -> Optional[CategoryChannel]:
        """Optional[:class:`~qq.CategoryChannel`]: 此频道所属的类别。如果没有类别，则为 ``None``。
        """
        return self.guild.get_channel(self.category_id)  # type: ignore

    async def delete(self, *, reason: Optional[str] = None) -> None:
        await self._state.http.delete_channel(self.id, reason=reason)

    async def _clone_impl(
            self: GCH,
            base_attrs: Dict[str, Any],
            *,
            name: Optional[str] = None,
            reason: Optional[str] = None,
    ) -> GCH:
        base_attrs['parent_id'] = self.category_id
        base_attrs['name'] = name or self.name
        guild_id = self.guild.id
        cls = self.__class__
        data = await self._state.http.create_channel(guild_id, self.type.value, reason=reason, **base_attrs)
        obj = cls(state=self._state, guild=self.guild, data=data)

        # temporarily add it to the cache
        self.guild._channels[obj.id] = obj  # type: ignore
        return obj

    async def clone(self: GCH, *, name: Optional[str] = None, reason: Optional[str] = None) -> GCH:
        raise NotImplementedError

    @overload
    async def move(
            self,
            *,
            beginning: bool,
            offset: int = MISSING,
            category: Optional[int] = MISSING,
            sync_permissions: bool = MISSING,
            reason: Optional[str] = MISSING,
    ) -> None:
        ...

    @overload
    async def move(
            self,
            *,
            end: bool,
            offset: int = MISSING,
            category: Optional[int] = MISSING,
            sync_permissions: bool = MISSING,
            reason: str = MISSING,
    ) -> None:
        ...

    @overload
    async def move(
            self,
            *,
            before: int,
            offset: int = MISSING,
            category: Optional[int] = MISSING,
            sync_permissions: bool = MISSING,
            reason: str = MISSING,
    ) -> None:
        ...

    @overload
    async def move(
            self,
            *,
            after: int,
            offset: int = MISSING,
            category: Optional[int] = MISSING,
            sync_permissions: bool = MISSING,
            reason: str = MISSING,
    ) -> None:
        ...

    async def move(self, **kwargs) -> None:
        """|coro|
        帮助你相对于其他频道移动频道。
        如果需要精确的位置移动，则应使用 ``edit`` 代替。

        Parameters
        ------------
        beginning: :class:`bool`
            是否将频道移动到频道列表（或类别，如果给定）的开头。这与 ``end`` 、 ``before`` 和 ``after`` 是互斥的。
        end: :class:`bool`
            是否将频道移动到频道列表（或类别，如果给定）的末尾。这与 ``beginning`` 、 ``before`` 和 ``after`` 是互斥的。
        before: :class:`GuildChannel`
            应该在我们当前频道之前的频道。这与 ``beginning`` 、 ``end`` 和` `after`` 是互斥的。
        after: :class:`GuildChannel`
            应该在我们当前频道之后的频道。这与 ``beginning`` 、 ``end`` 和 ``before`` 是互斥的。
        offset: :class:`int`
            偏移移动的通道数。
            例如，带有 ``beginning=True`` 的 ``2`` 偏移量会在开始后移动 2。
            正数将其移至下方，而负数将其移至上方。请注意，这个数字是相对的，并且是在 ``beginning`` 、 ``end`` 、 ``before`` 和 ``after`` 参数之后计算的。
        category: Optional[:class:`GuildChannel`]
            将此频道移动到的类别。如果给出 ``None``，则将其移出类别。如果移动类别频道，则忽略此参数。

        Raises
        -------
        InvalidArgument
            给出了无效的位置或传递了错误的参数组合。
        Forbidden
            您无权移动频道。
        HTTPException
            移动频道失败。
        """

        if not kwargs:
            return

        beginning, end = kwargs.get('beginning'), kwargs.get('end')
        before, after = kwargs.get('before'), kwargs.get('after')
        offset = kwargs.get('offset', 0)
        if sum(bool(a) for a in (beginning, end, before, after)) > 1:
            raise InvalidArgument('只能使用 [before, after, end, begin] 之一。')

        bucket = self._sorting_bucket
        parent_id = kwargs.get('category', MISSING)
        # fmt: off
        channels: List[GuildChannel]
        if parent_id not in (MISSING, None):
            parent_id = parent_id.id
            channels = [ch for ch in self.guild.channels
                        if ch._sorting_bucket == bucket and ch.category_id == parent_id]
        else:
            channels = [ch for ch in self.guild.channels
                        if ch._sorting_bucket == bucket and ch.category_id == self.category_id]
        # fmt: on

        channels.sort(key=lambda c: (c.position, c.id))

        try:
            # Try to remove ourselves from the channel list
            channels.remove(self)
        except ValueError:
            # If we're not there then it's probably due to not being in the category
            pass

        index = None
        if beginning:
            index = 0
        elif end:
            index = len(channels)
        elif before:
            index = next((i for i, c in enumerate(channels) if c.id == before.id), None)
        elif after:
            index = next((i + 1 for i, c in enumerate(channels) if c.id == after.id), None)

        if index is None:
            raise InvalidArgument('无法解析适当的移动位置')

        channels.insert(max((index + offset), 0), self)
        payload = []
        for index, channel in enumerate(channels):
            d = {'id': channel.id, 'position': index}
            if parent_id is not MISSING and channel.id == self.id:
                d.update(parent_id=parent_id)
            payload.append(d)

        await asyncio.gather(*self._state.http.bulk_channel_update(self.guild.id, payload))
