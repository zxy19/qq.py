from __future__ import annotations

import base64
from typing import Optional, TYPE_CHECKING, Union

import os
import io

__all__ = (
    'File',
)


class File:
    r"""用于 :meth:`abc.Messageable.send` 的参数对象，用于发送文件对象。

    .. note::

        文件对象是一次性的，不能在多个 :meth:`abc.Messageable.send` 中重复使用。

    .. warning::

        本功能尚未被官方实现，实现为 Discord 的实现

    Attributes
    -----------
    fp: Union[:class:`os.PathLike`, :class:`io.BufferedIOBase`]
        以二进制模式和读取模式打开的类文件对象或表示硬盘中要打开的文件的文件名。

        .. note::

            如果传递的类文件对象是通过 ``open`` 打开的，则应使用 ``rb`` 模式。 要传递二进制数据，请考虑使用 ``io.BytesIO``。

    filename: Optional[:class:`str`]
        上传到 QQ 时显示的文件名。
        如果没有给出，那么它默认为 ``fp.name`` 或者如果 ``fp`` 是一个字符串，那么 ``filename`` 将默认为给定的字符串。
    """

    __slots__ = ('fp', 'filename', '_original_pos', '_owner', '_closer')

    if TYPE_CHECKING:
        fp: io.BufferedIOBase
        filename: Optional[str]

    def __init__(
        self,
        fp: Union[str, bytes, os.PathLike, io.BufferedIOBase],
        filename: Optional[str] = None,
    ):
        if isinstance(fp, io.IOBase):
            if not (fp.seekable() and fp.readable()):
                raise ValueError(f'File buffer {fp!r} must be seekable and readable')
            self.fp = fp
            self._original_pos = fp.tell()
            self._owner = False
        else:
            self.fp = open(fp, 'rb')
            self._original_pos = 0
            self._owner = True

        # aiohttp only uses two methods from IOBase
        # read and close, since I want to control when the files
        # close, I need to stub it so it doesn't close unless
        # I tell it to
        self._closer = self.fp.close
        self.fp.close = lambda: None

        if filename is None:
            if isinstance(fp, str):
                _, self.filename = os.path.split(fp)
            else:
                self.filename = getattr(fp, 'name', None)
        else:
            self.filename = filename

    def reset(self, *, seek: Union[int, bool] = True) -> None:
        if seek:
            self.fp.seek(self._original_pos)

    def close(self) -> None:
        self.fp.close = self._closer
        if self._owner:
            self._closer()
