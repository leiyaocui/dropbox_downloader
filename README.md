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
python dropbox_downloader.py --link LINK --save-dir SAVE_DIR [--token TOKEN]

options:
  --link LINK          Shared link to download from Dropbox
  --save-dir SAVE_DIR  Local directory to save files
  --token TOKEN        Access token
```

## Features
- Check integrity
- Skip existing files

## TODO
- [ ] Recursively download subfolders
