import asyncio
import os
import mimetypes
import logging
from typing import List, Optional
from urllib.parse import urlparse

import uuid
from utils.outbound_http import SecureClientSession, safe_url_for_log


LOGGER = logging.getLogger(__name__)
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024


async def download_file(
    url: str, save_directory: str, headers: Optional[dict] = None
) -> Optional[str]:
    try:
        os.makedirs(save_directory, exist_ok=True)

        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)

        async with SecureClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                max_response_bytes=MAX_DOWNLOAD_BYTES,
            ) as response:
                if response.status != 200:
                    LOGGER.warning(
                        "File download failed: origin=%s status=%s",
                        safe_url_for_log(url),
                        response.status,
                    )
                    return None
                if not filename or "." not in filename:
                    content_disposition = response.headers.get(
                        "Content-Disposition", ""
                    )
                    if "filename=" in content_disposition:
                        filename = os.path.basename(
                            content_disposition.split("filename=")[1].strip("\"'")
                        )
                    else:
                        content_type = response.headers.get("Content-Type", "")
                        if content_type:
                            extension = mimetypes.guess_extension(
                                content_type.split(";")[0]
                            )
                            if extension:
                                filename = f"{uuid.uuid4()}{extension}"
                filename = os.path.basename(filename or str(uuid.uuid4()))
                save_path = os.path.join(save_directory, filename)
                with open(save_path, "wb") as file:
                    file.write(await response.read())
                LOGGER.info("File download completed: origin=%s", safe_url_for_log(url))
                return save_path

    except Exception:
        LOGGER.exception("File download failed: origin=%s", safe_url_for_log(url))
        return None


async def download_files(
    urls: List[str], save_directory: str, headers: Optional[dict] = None
) -> List[Optional[str]]:
    print(f"Starting download of {len(urls)} files to {save_directory}")
    coroutines = [download_file(url, save_directory, headers) for url in urls]
    results = await asyncio.gather(*coroutines, return_exceptions=True)
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Exception during download of {urls[i]}: {result}")
            final_results.append(None)
        else:
            final_results.append(result)

    successful_downloads = sum(1 for result in final_results if result is not None)
    print(
        f"Download completed: {successful_downloads}/{len(urls)} files downloaded successfully"
    )

    return final_results
