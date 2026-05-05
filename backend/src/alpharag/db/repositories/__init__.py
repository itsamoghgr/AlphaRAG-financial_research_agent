"""Repositories: the only modules that issue SQL.

Each repo wraps queries for one aggregate. Higher layers (services) call
repos; routers never call repos directly.
"""
