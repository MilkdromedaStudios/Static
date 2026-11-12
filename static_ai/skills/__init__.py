from .base import Registry
from .browser import register as register_browser
from .files import register as register_files
from .planning import register as register_planning
from .productivity import register as register_productivity
from .web import register as register_web


def create_registry():
    registry = Registry()
    for install in (register_web, register_files, register_planning, register_productivity, register_browser):
        install(registry)
    return registry
