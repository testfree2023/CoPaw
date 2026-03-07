# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long
import os
from pathlib import Path
from typing import Optional

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ...constant import WORKING_DIR
from ..schema import FileBlock


async def _create_file_block(file_path: str, file_name: str) -> Optional[FileBlock]:
    """Create a FileBlock for native channel file delivery.

    Args:
        file_path: Absolute file path
        file_name: File name for display

    Returns:
        FileBlock instance or None if creation fails
    """
    try:
        # Use file:// URL for local file access
        absolute_path = os.path.abspath(file_path)
        file_url = f"file://{absolute_path}"
        return FileBlock(
            type="file",
            source={"type": "url", "url": file_url},
            filename=file_name,
        )
    except Exception:
        return None


def _resolve_file_path(file_path: str) -> str:
    """Resolve file path: use absolute path as-is,
    resolve relative path from WORKING_DIR.

    Args:
        file_path: The input file path (absolute or relative).

    Returns:
        The resolved absolute file path as string.
    """
    path = Path(file_path)
    if path.is_absolute():
        return str(path)
    else:
        return str(WORKING_DIR / file_path)


async def read_file(  # pylint: disable=too-many-return-statements
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> ToolResponse:
    """Read a file. Relative paths resolve from WORKING_DIR.

    Use start_line/end_line to read a specific line range (output includes
    line numbers). Omit both to read the full file.

    Args:
        file_path (`str`):
            Path to the file.
        start_line (`int`, optional):
            First line to read (1-based, inclusive).
        end_line (`int`, optional):
            Last line to read (1-based, inclusive).
    """

    file_path = _resolve_file_path(file_path)

    if not os.path.exists(file_path):
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: The file {file_path} does not exist.",
                ),
            ],
        )

    if not os.path.isfile(file_path):
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: The path {file_path} is not a file.",
                ),
            ],
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        range_requested = start_line is not None or end_line is not None

        if range_requested:
            total = len(all_lines)
            s = max(1, start_line if start_line is not None else 1)
            e = min(total, end_line if end_line is not None else total)

            if s > total:
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text=(
                                f"Error: start_line {s} exceeds file length "
                                f"({total} lines) in {file_path}."
                            ),
                        ),
                    ],
                )

            if s > e:
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text=(
                                f"Error: start_line ({s}) is greater than "
                                f"end_line ({e}) in {file_path}."
                            ),
                        ),
                    ],
                )

            selected = all_lines[s - 1 : e]
            content = "".join(selected)
            header = f"{file_path}  (lines {s}-{e} of {total})\n"
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=header + content,
                    ),
                ],
            )
        else:
            content = "".join(all_lines)
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=content,
                    ),
                ],
            )

    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: Read file failed due to \n{e}",
                ),
            ],
        )


async def write_file(
    file_path: str,
    content: str,
) -> ToolResponse:
    """Create or overwrite a file. Relative paths resolve from WORKING_DIR.

    Args:
        file_path (`str`):
            Path to the file.
        content (`str`):
            Content to write.
    """

    if not file_path:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="Error: No `file_path` provide.",
                ),
            ],
        )

    file_path = _resolve_file_path(file_path)

    try:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)

        # Get relative path for download URL
        try:
            relative_path = Path(file_path).relative_to(WORKING_DIR)
            download_url = f"/api/workspace/files/{str(relative_path)}"
            file_name = relative_path.name
        except ValueError:
            # File is outside WORKING_DIR, no download URL
            download_url = None
            file_name = Path(file_path).name

        # Build response parts
        response_parts = [
            TextBlock(
                type="text",
                text=f"Wrote {len(content)} bytes to `{file_path}`.",
            ),
        ]

        # Add FileBlock for channels that support native file delivery
        # (dingtalk, feishu, etc. will upload and send as native file)
        file_block = await _create_file_block(file_path, file_name)
        if file_block:
            response_parts.append(file_block)

        # Add markdown download link for Console Web
        if download_url:
            response_parts.append(
                TextBlock(
                    type="text",
                    text=f"\n\n📥 [下载文件：{file_name}]({download_url})",
                ),
            )

        return ToolResponse(
            content=response_parts,
        )
    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: Write file failed due to \n{e}",
                ),
            ],
        )


async def edit_file(
    file_path: str,
    old_text: str,
    new_text: str,
) -> ToolResponse:
    """Find-and-replace text in a file. All occurrences of old_text are
    replaced with new_text. Relative paths resolve from WORKING_DIR.

    Args:
        file_path (`str`):
            Path to the file.
        old_text (`str`):
            Exact text to find.
        new_text (`str`):
            Replacement text.
    """

    response = await read_file(file_path=file_path)
    if response.content and len(response.content) > 0:
        error_text = response.content[0].get("text", "")
        if error_text.startswith("Error:"):
            return response
    if not response.content or len(response.content) == 0:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: Failed to read file {file_path}.",
                ),
            ],
        )

    content = response.content[0].get("text", "")
    if old_text not in content:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: The text to replace was not found in {file_path}.",
                ),
            ],
        )

    new_content = content.replace(old_text, new_text)
    write_response = await write_file(file_path=file_path, content=new_content)

    if write_response.content and len(write_response.content) > 0:
        write_text = write_response.content[0].get("text", "")
        if write_text.startswith("Error:"):
            return write_response

    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=f"Successfully replaced text in {file_path}.",
            ),
        ],
    )


async def append_file(
    file_path: str,
    content: str,
) -> ToolResponse:
    """Append content to the end of a file. Relative paths resolve from
    WORKING_DIR.

    Args:
        file_path (`str`):
            Path to the file.
        content (`str`):
            Content to append.
    """

    if not file_path:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="Error: No `file_path` provide.",
                ),
            ],
        )

    file_path = _resolve_file_path(file_path)

    try:
        with open(file_path, "a", encoding="utf-8") as file:
            file.write(content)
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Appended {len(content)} bytes to {file_path}.",
                ),
            ],
        )
    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: Append file failed due to \n{e}",
                ),
            ],
        )
