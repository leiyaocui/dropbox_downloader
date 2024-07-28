# Dropbox Downloader
Download files from a shared dropbox folder link.

# Requirements
1. Install Python packages (verified on Python 3.10).
```shell
pip install dropbox
```
2. Get an access token from this [link](https://www.dropbox.com/developers/apps).

# Usage
```shell
python dropbox_downloader.py --app-key APP_KEY --app-secret APP_SECRET [--retry RETRY] --link LINK --save-dir SAVE_DIR

args:
  --app-key APP_KEY     App key (see https://www.dropbox.com/developers/apps)
  --app-secret APP_SECRET
                        App secret (see https://www.dropbox.com/developers/apps)
  --retry RETRY         Number of retries for download
  --link LINK           Shared folder link to download from Dropbox
  --save-dir SAVE_DIR   Local directory to save files
```

## Features
- Check integrity
- Skip existing files

## TODO
- [ ] Recursively download subfolders
