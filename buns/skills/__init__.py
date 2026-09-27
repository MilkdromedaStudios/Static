from .base import Registry
from .files import register as register_files
from .planning import register as register_planning
from .web import register as register_web


def create_registry():
    registry = Registry()
    for install in (register_web, register_files, register_planning):
        install(registry)
    return registry
