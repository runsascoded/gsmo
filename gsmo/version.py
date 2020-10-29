
def get_version():
    from pkg_resources import get_distribution
    pkg = get_distribution('gsmo')
    return pkg.version
