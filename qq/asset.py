from __future__ import annotations

import io
import os
from typing import Any, Literal, Optional, TYPE_CHECKING, Tuple, Union
from .error import QQException
from . import utils

__all__ = (
    'Asset',
)

if TYPE_CHECKING:
    ValidStaticFormatTypes = Literal['webp', 'jpeg', 'jpg', 'png']
    ValidAssetFormatTypes = Literal['webp', 'jpeg', 'jpg', 'png', 'gif']

VALID_STATIC_FORMATS = frozenset({"jpeg", "jpg", "webp", "png"})
VALID_ASSET_FORMATS = VALID_STATIC_FORMATS | {"gif"}

MISSING = utils.MISSING


class AssetMixin:
    url: str
    _state: Optional[Any]

    async def read(self) -> bytes:
        """|coro|
        获得这个素材的 :class:`bytes` 内容。

        Raises
        ------
        QQException
            没有内部连接状态。
        HTTPException
            下载素材失败。
        NotFound
            素材已删除。
        Returns
        -------
        :class:`bytes`
            素材的内容。
        """

        if self._state is None:
            raise QQException('Invalid state (no ConnectionState provided)')

        return await self._state.http.get_from_cdn(self.url)

    async def save(self, fp: Union[str, bytes, os.PathLike, io.BufferedIOBase], *, seek_begin: bool = True) -> int:
        """|coro|
        将此素材保存到类似文件的对象中。

        Parameters
        ----------
        fp: Union[:class:`io.BufferedIOBase`, :class:`os.PathLike`]
            将此附件保存到的类文件对象或要使用的文件名。
            如果传递了文件名，则会使用该文件名创建一个文件并改为使用该文件。
        seek_begin: :class:`bool`
            保存成功后是否查找文件开头。

        Raises
        ------
        QQException
            没有内部连接状态。
        HTTPException
            下载素材失败。
        NotFound
            素材已删除。

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


class Asset(AssetMixin):
    """代表 QQ 上的素材。

    .. container:: operations

        .. describe:: str(x)

            返回素材的 URL。

        .. describe:: len(x)

            返回素材 URL 的长度。

        .. describe:: x == y

            检查素材是否等于另一个素材。

        .. describe:: x != y

            检查素材是否不等于另一个素材。

        .. describe:: hash(x)

            返回素材的哈希值。
    """

    __slots__: Tuple[str, ...] = (
        '_state',
        '_url',
        '_key',
    )

    def __init__(self, state, *, url: str, key: str):
        self._state = state
        self._url = url
        self._key = key

    @classmethod
    def _from_avatar(cls, state, avatar: str) -> Asset:
        return cls(
            state,
            url=avatar,
            key=avatar,
        )

    @classmethod
    def _from_guild_icon(cls, state, avatar: str) -> Asset:
        return cls(
            state,
            url=avatar,
            key=avatar,
        )

    def __str__(self) -> str:
        return self._url

    def __len__(self) -> int:
        return len(self._url)

    def __repr__(self):
        shorten = self._url.replace(self.BASE, '')
        return f'<Asset url={shorten!r}>'

    def __eq__(self, other):
        return isinstance(other, Asset) and self._url == other._url

    def __hash__(self):
        return hash(self._url)

    @property
    def url(self) -> str:
        """:class:`str`: 返回素材的底层 URL。"""
        return self._url

    @property
    def key(self) -> str:
        """:class:`str`: 返回素材的识别键。"""
        return self._key