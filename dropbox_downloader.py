import argparse
import hashlib
from pathlib import Path
from typing import List

import dropbox
import dropbox.files
import six


class DropboxContentHasher:
    """
    Computes a hash using the same algorithm that the Dropbox API uses for the
    the "content_hash" metadata field.

    The digest() method returns a raw binary representation of the hash.  The
    hexdigest() convenience method returns a hexadecimal-encoded version, which
    is what the "content_hash" metadata field uses.

    This class has the same interface as the hashers in the standard 'hashlib'
    package.

    Example:

        hasher = DropboxContentHasher()
        with open('some-file', 'rb') as f:
            while True:
                chunk = f.read(1024)  # or whatever chunk size you want
                if len(chunk) == 0:
                    break
                hasher.update(chunk)
        print(hasher.hexdigest())

    from https://github.com/dropbox/dropbox-api-content-hasher/blob/master/python/dropbox_content_hasher.py
    """

    BLOCK_SIZE = 4 * 1024 * 1024

    def __init__(self):
        self._overall_hasher = hashlib.sha256()
        self._block_hasher = hashlib.sha256()
        self._block_pos = 0

        self.digest_size = self._overall_hasher.digest_size
        # hashlib classes also define 'block_size', but I don't know how people use that value

    def update(self, new_data):
        if self._overall_hasher is None:
            raise AssertionError(
                "can't use this object anymore; you already called digest()"
            )

        assert isinstance(
            new_data, six.binary_type
        ), "Expecting a byte string, got {!r}".format(new_data)

        new_data_pos = 0
        while new_data_pos < len(new_data):
            if self._block_pos == self.BLOCK_SIZE:
                self._overall_hasher.update(self._block_hasher.digest())
                self._block_hasher = hashlib.sha256()
                self._block_pos = 0

            space_in_block = self.BLOCK_SIZE - self._block_pos
            part = new_data[new_data_pos : (new_data_pos + space_in_block)]
            self._block_hasher.update(part)

            self._block_pos += len(part)
            new_data_pos += len(part)

    def _finish(self):
        if self._overall_hasher is None:
            raise AssertionError(
                "can't use this object anymore; you already called digest() or hexdigest()"
            )

        if self._block_pos > 0:
            self._overall_hasher.update(self._block_hasher.digest())
            self._block_hasher = None
        h = self._overall_hasher
        self._overall_hasher = None  # Make sure we can't use this object anymore.
        return h

    def digest(self):
        return self._finish().digest()

    def hexdigest(self):
        return self._finish().hexdigest()

    def copy(self):
        c = DropboxContentHasher.__new__(DropboxContentHasher)
        c._overall_hasher = self._overall_hasher.copy()
        c._block_hasher = self._block_hasher.copy()
        c._block_pos = self._block_pos
        return c


def authorize_dropbox(app_key: str, app_secret: str):
    print("\n==== Authorizing Dropbox ====")
    flow = dropbox.DropboxOAuth2FlowNoRedirect(
        app_key, app_secret, token_access_type="offline"
    )
    authorize_url = flow.start()
    print("1. Go to: " + authorize_url)
    print("2. Click 'Allow' (you might have to log in first)")
    print("3. Copy the authorization code")
    auth_code = input("Enter the authorization code here: ").strip()
    auth_res = flow.finish(auth_code)

    dbx = dropbox.Dropbox(
        oauth2_access_token=auth_res.access_token,
        oauth2_refresh_token=auth_res.refresh_token,
        oauth2_access_token_expiration=auth_res.expires_at,
        app_key=args.app_key,
        app_secret=args.app_secret,
    )
    return dbx


def check_file_hash(file_path: Path, expected_hash: str):
    hasher = DropboxContentHasher()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(hasher.BLOCK_SIZE)
            if len(chunk) == 0:
                break
            hasher.update(chunk)
    return hasher.hexdigest() == expected_hash


def fetch_entries(dbx: dropbox.Dropbox, link: str, save_dir: Path):
    print("\n==== Fetching entries to download ====")
    link = dropbox.files.SharedLink(url=link)
    entries_to_download, total_size, total_num = [], 0, 0
    res = dbx.files_list_folder(path="", shared_link=link)
    while True:
        entries = res.entries
        total_num += len(entries)
        for entry in entries:
            if isinstance(entry, dropbox.files.FileMetadata):
                save_path = save_dir / entry.name
                if save_path.exists() and save_path.stat().st_size == entry.size:
                    if check_file_hash(save_path, entry.content_hash):
                        print(f"Skipping: {entry.name} (already downloaded)", end="\r")
                        continue
                total_size += entry.size
                entries_to_download.append(entry)
            elif isinstance(entry, dropbox.files.FolderMetadata):
                # TODO: Support recursive download
                raise NotImplementedError("Recursive download is not supported yet")
            else:
                raise ValueError(f"Unknown entry type: {type(entry)}")
            print(
                f"Found {len(entries_to_download)}/{total_num} files to download",
                end="\r",
            )

        if not res.has_more:
            break
        res = dbx.files_list_folder_continue(res.cursor)

    print(
        f"Found {len(entries_to_download)}/{total_num} files ({total_size} bytes) to download"
    )
    return entries_to_download


def download_entries(
    dbx: dropbox.Dropbox,
    entries: List[dropbox.files.FileMetadata],
    link: str,
    save_dir: Path,
    retry: int = 5,
):
    print("\n==== Downloading entries ====")
    for idx, entry in enumerate(entries):
        save_path = save_dir / entry.name
        for retry_i in range(retry):
            try:
                print(f"Downloading {idx + 1}/{len(entries)}: {entry.name}", end="\r")
                dbx.sharing_get_shared_link_file_to_file(
                    save_path, link, f"/{entry.name}"
                )
                if not check_file_hash(save_path, entry.content_hash):
                    save_path.unlink()
                    raise ValueError("Downloaded {entry.name} hash does not match")
                break
            except Exception as e:
                if retry_i < retry - 1:
                    if dbx.check_and_refresh_access_token():
                        print("Access token refreshed. Retrying...", end="\r")
                    else:
                        print(
                            f"Failed to download {entry.name}: {e}. Retrying...",
                            end="\r",
                        )
                else:
                    print(f"Failed to download {entry.name}: {e}. Skipping...")
    print("Download completed")


def main(args):
    dbx = authorize_dropbox(args.app_key, args.app_secret)

    save_dir = Path(args.save_dir).absolute()
    print("\nSave directory:", save_dir)
    save_dir.mkdir(exist_ok=True, parents=True)

    entries = fetch_entries(dbx, args.link, save_dir)
    download_entries(dbx, entries, args.link, save_dir, args.retry)

    dbx.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--app-key",
        required=True,
        help="App key (see https://www.dropbox.com/developers/apps)",
    )
    parser.add_argument(
        "--app-secret",
        required=True,
        help="App secret (see https://www.dropbox.com/developers/apps)",
    )
    parser.add_argument(
        "--retry", type=int, default=5, help="Number of retries for download"
    )
    parser.add_argument(
        "--link", required=True, help="Shared folder link to download from Dropbox"
    )
    parser.add_argument(
        "--save-dir", required=True, help="Local directory to save files"
    )
    args = parser.parse_args()

    main(args)
