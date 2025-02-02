from __future__ import annotations

from typing import List, Literal, Optional, TypedDict, Union

from .embed import Embed
from .emoji import PartialEmoji
from .member import Member
from .user import User
from ..utils import SnowflakeList


class _AttachmentOptional(TypedDict, total=False):
    height: Optional[int]
    width: Optional[int]
    content_type: str


class Attachment(_AttachmentOptional):
    id: int
    filename: str
    size: int
    url: str


class _MessageOptional(TypedDict, total=False):
    guild_id: str


class Message(_MessageOptional):
    id: str
    channel_id: str
    author: User
    member: Member
    content: str
    timestamp: str
    edited_timestamp: Optional[str]
    mention_everyone: bool
    mentions: List[User]
    attachments: List[Attachment]
    embeds: List[Embed]


AllowedMentionType = Literal['roles', 'users', 'everyone']


class AllowedMentions(TypedDict):
    parse: List[AllowedMentionType]
    roles: SnowflakeList
    users: SnowflakeList
    replied_user: bool


class MessageReference(TypedDict, total=False):
    message_id: int
    channel_id: int
    guild_id: int
    fail_if_not_exists: bool


class Reaction(TypedDict):
    count: int
    me: bool
    emoji: PartialEmoji
