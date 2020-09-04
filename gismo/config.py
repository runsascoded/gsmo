
def strs(config, *keys):
    config = get(config, *keys)
    if config:
        if isinstance(config, list):
            return config
        return [ config ]
    return []


def get(config, *keys, default=None):
    keys = list(keys)
    if keys:
        key = keys.pop(0)
        if not config or not key in config:
            return default
        return get(config[key], *keys)

    return config


def get_name(config):
    if 'name' in config:
        return config['name']
    from pathlib import Path
    return Path.cwd().name
