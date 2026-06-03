"""Request/response Pydantic schemas (PRD §6, §8).

SQLModel table classes double as read schemas, but create/update requests use
dedicated models so read-only fields stay protected.
"""
