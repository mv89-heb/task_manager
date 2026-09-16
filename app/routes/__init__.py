"""Route package bootstrap.

The existing application registers the tasks blueprint from the application
factory. Importing mobile here attaches the dedicated mobile routes to that
same blueprint without changing the production application factory.
"""

from . import mobile  # noqa: F401,E402
