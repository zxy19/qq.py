from __future__ import annotations

import asyncio
import base64
import datetime
import io
import re
from os import PathLike
from typing import Union, Optional, TYPE_CHECKING, ClassVar, Tuple, List, Callable, overload, Any, Type, TypeVar

from . import utils
from .file import File
from .member import Member
from .mixins import Hashable
from .role import Role
from .utils import escape_mentions
from .guild import Guild
from .error import HTTPException

if TYPE_CHECKING:
    from .state import ConnectionState
    from .abc import GuildChannel, PartialMessageableChannel, MessageableChannel
    from .channel import TextChannel
    from .embeds import Embed
    from .enum import ChannelType
    from .types.message import Attachment as AttachmentPayload, Message as MessagePayload, \
        MessageReference as MessageReferencePayload
    from .types.embed import Embed as EmbedPayload
    from .types.user import User as UserPayload
    from .types.member import Member as MemberPayload, UserWithMember as UserWithMemberPayload
    from .user import User

    MR = TypeVar('MR', bound='MessageReference')


class MessageReference:
    """表示对 :class:`~qq.Message` 的引用。 这个类现在可以由用户构建。

    Attributes
    -----------
    message_id: Optional[:class:`int`]
        引用的消息的 ID。
    channel_id: :class:`int`
        引用的消息的子频道 ID。
    guild_id: Optional[:class:`int`]
        所引用消息的频道 ID。
    fail_if_not_exists: :class:`bool`
        回复引用的消息是否应该引发 :class:`HTTPException`
        如果消息不再存在或 QQ 无法获取消息。
    resolved: Optional[:class:`Message`]
        此引用将解析为的消息。 如果这是 ``None`` ，那么原始消息没有被获取，要么是因为 QQ API 没有尝试解析它，要么在创建时它不可用。

        目前，这主要是用户回复消息时的回复消息。
    """
    __slots__ = ('message_id', 'channel_id', 'guild_id', 'fail_if_not_exists', 'resolved', '_state')

    def __init__(self, *, message_id: int, channel_id: int, guild_id: Optional[int] = None,
                 fail_if_not_exists: bool = True):
        self._state: Optional[ConnectionState] = None
        self.resolved: Optional[Message] = None
        self.message_id: Optional[int] = message_id
        self.channel_id: int = channel_id
        self.guild_id: Optional[int] = guild_id
        self.fail_if_not_exists: bool = fail_if_not_exists

    @classmethod
    def with_state(cls: Type[MR], state: ConnectionState, data: MessageReferencePayload) -> MR:
        self = cls.__new__(cls)
        self.message_id = data.get('message_id')
        self.channel_id = int(data.pop('channel_id'))
        self.guild_id = data.get('guild_id')
        self.fail_if_not_exists = data.get('fail_if_not_exists', True)
        self._state = state
        self.resolved = None
        return self

    @classmethod
    def from_message(cls: Type[MR], message: Message, *, fail_if_not_exists: bool = True) -> MR:
        """从现有的 :class:`~qq.Message` 创建一个 :class:`MessageReference` 。

        Parameters
        ----------
        message: :class:`~qq.Message`
            要转换为引用的消息。
        fail_if_not_exists: :class:`bool`
            回复引用的消息是否应该引发 :class:`HTTPException`
            如果消息不再存在或 QQ 无法获取消息。

        Returns
        -------
        :class:`MessageReference`
            对消息的引用。
        """

        self = cls(
            message_id=message.id,
            channel_id=message.channel.id,
            guild_id=getattr(message.guild, 'id', None),
            fail_if_not_exists=fail_if_not_exists,
        )
        self._state = message._state
        return self

    @property
    def cached_message(self) -> Optional[Message]:
        """Optional[:class:`~qq.Message`]: 缓存的消息（如果在内部消息缓存中找到）。"""
        return self._state and self._state._get_message(self.message_id)

    def __repr__(self) -> str:
        return f'<MessageReference message_id={self.message_id!r} channel_id={self.channel_id!r} guild_id={self.guild_id!r}>'

    def to_dict(self) -> MessageReferencePayload:
        result: MessageReferencePayload = {'message_id': self.message_id} if self.message_id is not None else {}
        result['channel_id'] = self.channel_id
        if self.guild_id is not None:
            result['guild_id'] = self.guild_id
        if self.fail_if_not_exists is not None:
            result['fail_if_not_exists'] = self.fail_if_not_exists
        return result

    to_message_reference_dict = to_dict


class Attachment(Hashable):
    """代表来自 QQ 的附件。

    .. container:: operations
        .. describe:: str(x)
            返回附件的 URL。

    Attributes
    ------------
    id: :class:`int`
        附件的 ID。
    size: :class:`int`
        附件的大小。
    height: Optional[:class:`int`]
        附件的高度，只对视频和图片适用。
    width: Optional[:class:`int`]
        附件的宽度，只对视频和图片适用。
    filename: :class:`str`
        附件的文件名
    url: :class:`str`
        附件网址。 如果此附件被删除，则这将是 404。
    content_type: Optional[:class:`str`]
        附件的 `类型  <https://en.wikipedia.org/wiki/Media_type>`_
    """

    __slots__ = ('id', 'size', 'height', 'width', 'filename', 'url', '_http', 'content_type')

    def __init__(self, *, data: AttachmentPayload, state: ConnectionState):
        self.id: int = int(data['id'])
        self.size: int = data['size']
        self.height: Optional[int] = data.get('height')
        self.width: Optional[int] = data.get('width')
        self.filename: str = data['filename']
        self.url: str = 'https://' + data.get('url')\
                        if not data.get('url').startswith('https://') \
                        else data.get('url')
        self._http = state.http
        self.content_type: Optional[str] = data.get('content_type')

    def __repr__(self) -> str:
        return f'<Attachment id={self.id} filename={self.filename!r} url={self.url!r}>'

    def __str__(self) -> str:
        return self.url or ''

    async def save(
            self,
            fp: Union[io.BufferedIOBase, PathLike],
            *,
            seek_begin: bool = True,
    ) -> int:
        """|coro|
        将此附件保存到类文件对象中。

        Parameters
        -----------
        fp: Union[:class:`io.BufferedIOBase`, :class:`os.PathLike`]
            将此附件保存到的类文件对象或要使用的文件名。 如果传递了文件名，则会使用该文件名创建一个文件并改为使用该文件。
        seek_begin: :class:`bool`
            保存成功后是否查找文件开头。

        Raises
        --------
        HTTPException
            保存附件失败。
        NotFound
            附件已删除。

        Returns
        --------
        :class:`int`
            写入的字节数。
        """

        data = await self.read()
        if isinstance(fp, io.BufferedIOBase):
            written = fp.write(data)
            if seek_begin:
                fp.seek(0)
            return written
        else:
            with open(fp, 'wb') as f:
                return f.write(data)

    async def b64(self) -> str:
        byte = self.read()
        return 'base64://' + base64.b64encode(await byte).decode()

    async def read(self) -> bytes:
        """|coro|
        检索此附件的内容作为 :class:`bytes` 对象。

        Raises
        ------
        HTTPException
            下载附件失败。
        Forbidden
            你无权访问此附件
        NotFound
            附件已删除。

        Returns
        -------
        :class:`bytes`
            附件的内容。
        """

        url = self.url
        data = await self._http.get_from_cdn(url)
        return data

    async def to_file(self) -> File:
        """|coro|
        将附件转换为适合通过 :meth:`abc.Messageable.send` 发送的 :class:`File`。

        Raises
        ------
        HTTPException
            下载附件失败。
        Forbidden
            你无权访问此附件
        NotFound
            附件已删除。

        Returns
        -------
        :class:`File`
            附件作为适合发送的文件。
        """

        data = await self.read()
        return File(io.BytesIO(data), filename=self.filename)

    def to_dict(self) -> AttachmentPayload:
        result: AttachmentPayload = {
            'filename': self.filename,
            'id': self.id,
            'size': self.size,
            'url': self.url,
            'spoiler': self.is_spoiler(),
        }
        if self.height:
            result['height'] = self.height
        if self.width:
            result['width'] = self.width
        if self.content_type:
            result['content_type'] = self.content_type
        return result


def flatten_handlers(cls):
    prefix = len('_handle_')
    handlers = [
        (key[prefix:], value)
        for key, value in cls.__dict__.items()
        if key.startswith('_handle_') and key != '_handle_member'
    ]

    # store _handle_member last
    handlers.append(('member', cls._handle_member))
    cls._HANDLERS = handlers
    cls._CACHED_SLOTS = [attr for attr in cls.__slots__ if attr.startswith('_cs_')]
    return cls


@flatten_handlers
class Message(Hashable):
    r"""代表来自 QQ 的消息。

    .. container:: operations

        .. describe:: x == y

            检查两个消息是否相等。

        .. describe:: x != y

            检查两个消息是否不相等。

        .. describe:: hash(x)

            返回消息的哈希值。

    Attributes
    -----------
    author: Union[:class:`Member`, :class:`abc.User`]
        发送消息的 :class:`Member`。 如果用户离开了频道，那么它是一个 :class:`User` 。
    content: :class:`str`
        消息的实际内容。
    embeds: List[:class:`Embed`]
        消息所具有的 :class:`Embed` 的列表。
    channel: :class:`TextChannel`
        发送消息的 :class:`TextChannel`。
    mention_everyone: :class:`bool`
        指定消息是否提及所有人。

        .. note::

            这不会检查 ``@全体成员`` 文本是否在消息本身中。
            因此你需要在检查 ``@全体成员`` 文本是否在消息中 **的同时** 看这个是否是 ``True`` 。

    mentions: List[:class:`Member`]
        @到的 :class:`Member` 列表。

        .. warning::

            提及列表的顺序没有任何特定顺序，因此你不应依赖它。 这是 QQ 的限制，与库无关。

    channel_mentions: List[:class:`abc.GuildChannel`]
        提到的 :class:`abc.GuildChannel` 的列表。 (官方还没有实现)
    role_mentions: List[:class:`Role`]
        提到的 :class:`Role` 列表。 (官方还没有实现)
    id: :class:`int`
        消息ID。
    attachments: List[:class:`Attachment`]
        提供给消息的附件列表。
    guild: Optional[:class:`Guild`]
        消息所属的频道（如果适用）。
    """
    __slots__ = (
        '_state',
        '_edited_timestamp',
        '_cs_channel_mentions',
        '_cs_raw_mentions',
        '_cs_clean_content',
        '_cs_raw_channel_mentions',
        '_cs_system_content',
        'content',
        'channel',
        'mention_everyone',
        'embeds',
        'id',
        'mentions',
        'author',
        'attachments',
        'guild',
        'reference',
        'role_mentions',
        'created_at'
    )

    if TYPE_CHECKING:
        _HANDLERS: ClassVar[List[Tuple[str, Callable[..., None]]]]
        _CACHED_SLOTS: ClassVar[List[str]]
        guild: Optional[Guild]
        mentions: List[Union[User, Member]]
        author: Union[User, Member]
        role_mentions: List[Role]

    def __init__(
            self,
            *,
            state: ConnectionState,
            channel: MessageableChannel,
            data: MessagePayload,
    ):
        self._state: ConnectionState = state
        self.created_at = datetime.datetime.now()
        self.id: str = data['id']
        self.attachments: Optional[List[Attachment]] = \
            [Attachment(data=a, state=self._state) for a in data['attachments']] \
                if 'attachments' in data else None
        self.embeds: Optional[List[Embed]] = [Embed.from_dict(a) for a in data['embeds']] \
            if 'embeds' in data else None
        self.channel: MessageableChannel = channel
        self._edited_timestamp: Optional[datetime.datetime] = utils.parse_time(data['edited_timestamp']) \
            if 'edited_timestamp' in data else None
        self.mention_everyone: bool = data['mention_everyone'] \
            if 'mention_everyone' in data else None
        self.content: str = data['content']

        try:
            # if the channel doesn't have a guild attribute, we handle that
            self.guild = channel.guild  # type: ignore
        except AttributeError:
            self.guild = state._get_guild(data.get('guild_id'))

        for handler in ('author', 'member', 'mentions'):
            try:
                getattr(self, f'_handle_{handler}')(data[handler])
            except KeyError:
                continue

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return (
            f'<{name} id={self.id} channel={self.channel!r} type={self.type!r} author={self.author!r}>'
        )

    def _try_patch(self, data, key, transform=None) -> None:
        try:
            value = data[key]
        except KeyError:
            pass
        else:
            if transform is None:
                setattr(self, key, value)
            else:
                setattr(self, key, transform(value))

    def _update(self, data):
        # In an update scheme, 'author' key has to be handled before 'member'
        # otherwise they overwrite each other which is undesirable.
        # Since there's no good way to do this we have to iterate over every
        # handler rather than iterating over the keys which is a little slower
        for key, handler in self._HANDLERS:
            try:
                value = data[key]
            except KeyError:
                continue
            else:
                handler(self, value)

        # clear the cached properties
        for attr in self._CACHED_SLOTS:
            try:
                delattr(self, attr)
            except AttributeError:
                pass

    def _handle_edited_timestamp(self, value: str) -> None:
        self._edited_timestamp = utils.parse_time(value)

    def _handle_mention_roles(self, role_mentions: List[int]) -> None:
        self.role_mentions = []
        if isinstance(self.guild, Guild):
            for role_id in map(int, role_mentions):
                role = self.guild.get_role(role_id)
                if role is not None:
                    self.role_mentions.append(role)

    def _handle_mention_everyone(self, value: bool) -> None:
        self.mention_everyone = value

    def _handle_content(self, value: str) -> None:
        self.content = value

    def _handle_attachments(self, value: List[AttachmentPayload]) -> None:
        self.attachments = [Attachment(data=a, state=self._state) for a in value]

    def _handle_embeds(self, value: List[EmbedPayload]) -> None:
        self.embeds = [Embed.from_dict(data) for data in value]

    def _handle_author(self, author: UserPayload) -> None:
        self.author = self._state.store_user(author)
        self.guild._add_member(self.author)

    def _handle_member(self, member: MemberPayload) -> None:
        author = self.author
        try:
            # Update member reference
            author._update_from_message(member)  # type: ignore
        except AttributeError:
            # It's a user here
            self.author = Member._from_message(message=self, data=member)

    def _handle_mentions(self, mentions: List[UserWithMemberPayload]) -> None:
        self.mentions = r = []
        guild = self.guild
        state = self._state
        if not isinstance(guild, Guild):
            self.mentions = [state.store_user(m) for m in mentions]
            return

        for mention in filter(None, mentions):
            id_search = int(mention['id'])
            member = guild.get_member(id_search)
            if member is not None:
                r.append(member)
            else:
                r.append(Member._try_upgrade(data=mention, guild=guild, state=state))

    def _rebind_cached_references(self, new_guild: Guild, new_channel: TextChannel) -> None:
        self.guild = new_guild
        self.channel = new_channel

    @utils.cached_slot_property('_cs_raw_mentions')
    def raw_mentions(self) -> List[int]:
        """List[:class:`int`]: 返回与消息内容中的 ``<@user_id>`` 语法匹配的用户 ID 数组的属性。
        """
        return [int(x) for x in re.findall(r'<@!?([0-9]{15,20})>', self.content)]

    @utils.cached_slot_property('_cs_raw_channel_mentions')
    def raw_channel_mentions(self) -> List[int]:
        """List[:class:`int`]: 返回与消息内容中的 ``<#channel_id>`` 语法匹配的通道 ID 数组的属性。
        """
        return [int(x) for x in re.findall(r'<#([0-9]{15,20})>', self.content)]

    @utils.cached_slot_property('_cs_raw_role_mentions')
    def raw_role_mentions(self) -> List[int]:
        """List[:class:`int`]: 返回与消息内容中的 ``<@&role_id>`` 语法匹配的通道 ID 数组的属性。
        """
        return [int(x) for x in re.findall(r'<@&([0-9]{15,20})>', self.content)]

    @utils.cached_slot_property('_cs_channel_mentions')
    def channel_mentions(self) -> List[GuildChannel]:
        if self.guild is None:
            return []
        it = filter(None, map(self.guild.get_channel, self.raw_channel_mentions))
        return utils._unique(it)

    @utils.cached_slot_property('_cs_channel_mentions')
    def channel_mentions(self) -> List[GuildChannel]:
        if self.guild is None:
            return []
        it = filter(None, map(self.guild.get_channel, self.raw_channel_mentions))
        return utils._unique(it)

    @utils.cached_slot_property('_cs_clean_content')
    def clean_content(self) -> str:
        """:class:`str`:

        以“清理”方式返回内容的属性。 这代表把提及转换成客户展示它的方式。 例如 ``<#id>`` 将转换为 ``#name``。
        这也会将 @全体成员 提及转换为未提及。

        .. note::

        这 **不** 影响 Markdown 。
        如果你想转义或删除 Markdown，请分别使用 :func:`utils.escape_markdown` 或 :func:`utils.remove_markdown` 以及此功能。

        """

        # fmt: off
        transformations = {
            re.escape(f'<#{channel.id}>'): '#' + channel.name
            for channel in self.channel_mentions
        }

        mention_transforms = {
            re.escape(f'<@{member.id}>'): '@' + member.display_name
            for member in self.mentions
        }

        # add the <@!user_id> cases as well..
        second_mention_transforms = {
            re.escape(f'<@!{member.id}>'): '@' + member.display_name
            for member in self.mentions
        }

        transformations.update(mention_transforms)
        transformations.update(second_mention_transforms)

        if self.guild is not None:
            role_transforms = {
                re.escape(f'<@&{role.id}>'): '@' + role.name
                for role in self.role_mentions
            }
            transformations.update(role_transforms)

        # fmt: on

        def repl(obj):
            return transformations.get(re.escape(obj.group(0)), '')

        pattern = re.compile('|'.join(transformations.keys()))
        result = pattern.sub(repl, self.content)
        return escape_mentions(result)

    @property
    def edited_at(self) -> Optional[datetime.datetime]:
        return self._edited_timestamp

    async def reply(self, content: Optional[str] = None, **kwargs) -> Message:
        return await self.channel.send(content, reference=self, **kwargs)

    def to_reference(self, *, fail_if_not_exists: bool = True) -> MessageReference:
        """从当前消息创建一个 :class:`~qq.MessageReference`。

        Parameters
        ----------
        fail_if_not_exists: :class:`bool`
            如果消息不再存在或 QQ 无法获取消息，使用消息引用回复是否应该引发 :class:`HTTPException`

        Returns
        ---------
        :class:`~qq.MessageReference`
            对此消息的引用。
        """

        return MessageReference.from_message(self, fail_if_not_exists=fail_if_not_exists)

    def to_message_reference_dict(self) -> MessageReferencePayload:
        data: MessageReferencePayload = {
            'message_id': self.id,
            'channel_id': self.channel.id,
        }

        if self.guild is not None:
            data['guild_id'] = self.guild.id

        return data


class PartialMessage(Hashable):
    """当仅存在消息和通道 ID 时，只使用部分消息以帮助处理消息。
    有两种方法可以构造这个类。第一个是通过构造函数本身，第二个是通过以下方式：

    - :meth:`TextChannel.get_partial_message`

    注意这个类是被修剪过的，没有丰富的属性。

    .. container:: operations

        .. describe:: x == y
            检查两个部分消息是否相等。
        .. describe:: x != y
            检查两个部分消息是否不相等。
        .. describe:: hash(x)
            返回部分消息的哈希值。

    Attributes
    -----------
    channel: :class:`TextChannel`
        与此部分消息关联的频道。
    id: :class:`int`
        消息 ID。
    """

    __slots__ = ('channel', 'id', '_cs_guild', '_state')

    def __init__(self, *, channel: PartialMessageableChannel, id: int):
        if channel.type not in (
                ChannelType.text,
        ):
            raise TypeError(f'Expected TextChannel,not {type(channel)!r}')

        self.channel: PartialMessageableChannel = channel
        self._state: ConnectionState = channel._state
        self.id: int = id

    def _update(self, data) -> None:
        # This is used for duck typing purposes.
        # Just do nothing with the data.
        pass

    # Also needed for duck typing purposes
    # n.b. not exposed

    def __repr__(self) -> str:
        return f'<PartialMessage id={self.id} channel={self.channel!r}>'

    @utils.cached_slot_property('_cs_guild')
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`Guild`]: 部分消息所属的频道（如果适用）。"""
        return getattr(self.channel, 'guild', None)

    async def fetch(self) -> Message:
        """|coro|
        将部分消息获取到完整的 :class:`Message` 。

        Raises
        --------
        NotFound
            未找到该消息。
        Forbidden
            你没有获取消息所需的权限。
        HTTPException
            检索消息失败。
        Returns
        --------
        :class:`Message`
            完整的消息。
        """

        data = await self._state.http.get_message(self.channel.id, self.id)
        return self._state.create_message(channel=self.channel, data=data)
