"""HTTP API package.

Import ``create_app`` from ``src.api.main`` when constructing the server.
Keeping package initialization side-effect free prevents UI clients from
creating a local database merely by importing the API client.
"""
