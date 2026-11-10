#!/usr/bin/env python3
from plugin_tools import validate

if __name__ == '__main__':
    manifest = validate()
    print(f'PLUGIN_CONTENT_VALID: {manifest["name"]} {manifest["version"]}')
