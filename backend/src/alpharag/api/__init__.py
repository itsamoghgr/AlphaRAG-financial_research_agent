"""HTTP layer. Routers are thin: they validate input, call a service, and
shape the response. They never touch repositories or external services
directly.
"""
