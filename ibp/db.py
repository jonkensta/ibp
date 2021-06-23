"""Database engine bindings and session-maker."""

import urllib

import sqlalchemy  # type: ignore
from sqlalchemy.orm import sessionmaker  # type: ignore

import pymates  # type: ignore

from .models import Inmate
from .base import get_toplevel_path


def create_engine():
    """Create an engine for our sqlite database."""
    toplevel = get_toplevel_path()
    filepath = toplevel.joinpath("data.db").absolute()
    uri_parts = ("sqlite", "/", str(filepath), "", "", "")  # netloc needs to be "/".
    uri = urllib.parse.urlunparse(uri_parts)
    return sqlalchemy.create_engine(uri)


def build_sessionmaker():
    """Build a sessionmaker for our sqlite database."""
    return sessionmaker(bind=create_engine())


Session = build_sessionmaker()


# pylint: disable=redefined-builtin, invalid-name
def query_providers_by_id(session, id: int):
    """Query inmate providers with an inmate ID.

    :param id: Inmate TDCJ or FBOP ID to search.
    :type id: int

    :returns: tuple of (:py:data:`inmates`, :py:data:`errors`) where

        - :py:data:`inmates` is a QueryResult for the inmate search.
        - :py:data:`errors` is a list of error strings.

    """
    inmates, errors = pymates.query_by_inmate_id(id)
    inmates = (Inmate.from_response(session, inmate) for inmate in inmates)

    with session.begin_nested():
        for inmate in inmates:
            assert inmate not in session
            session.merge(inmate)

    inmates = session.query(Inmate).filter_by(id=id)
    return inmates, errors


def query_providers_by_name(session, first_name: str, last_name: str):
    """Query inmate providers with an inmate ID.

    :param first_name: Inmate first name to search.
    :type first_name: str

    :param last_name: Inmate last name to search.
    :type last_name: str

    :returns: tuple of (:py:data:`inmates`, :py:data:`errors`) where

        - :py:data:`inmates` is a QueryResult for the inmate search.
        - :py:data:`errors` is a list of error strings.

    """
    inmates, errors = pymates.query_by_name(first_name, last_name)
    inmates = (Inmate.from_response(session, inmate) for inmate in inmates)

    with session.begin_nested():
        for inmate in inmates:
            assert inmate not in session
            session.merge(inmate)

    tolower = sqlalchemy.func.lower
    inmates = session.query(Inmate)
    inmates = inmates.filter(tolower(Inmate.last_name) == tolower(last_name))
    inmates = inmates.filter(Inmate.first_name.ilike(first_name + "%"))

    return inmates, errors
