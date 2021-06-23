""":py:mod:`sqlalchemy` models used for the IBP database.

The following classes model the database abstraction used by IBP for its SQLite
database. These relate to the day-to-day IBP logistics, including:

    * recording results of searches for inmates through :py:class:`Inmate`,
    * recording volunteer lookups for inmates through :py:class:`Lookup`,
    * recording volunteer comments on inmates through :py:class:`Comment`,
    * processing book requests from inmates through :py:class:`Request`,
    * recording package shipments through :py:class:`Shipment`,
    * recording unit jurisdiction and address information through :py:class:`Unit`

In addition to the models, this module also defines a few convenience items:

    * Special column types :py:data:`Jurisdiction`, :py:class:`ReleaseDate`
    * Inmate foreign-key mix-in :py:class:`HasInmateIndexKey`

These utility items are exported and documented but should not likely be used
anywhere else apart from here.

"""

# pylint: disable=too-few-public-methods, invalid-name

import typing
from datetime import datetime, timedelta

from sqlalchemy import (  # type: ignore
    Column,
    Enum,
    Text,
    Integer,
    String,
    DateTime,
    Date,
    ForeignKey,
)

from sqlalchemy.orm import relationship  # type: ignore
from sqlalchemy.processors import str_to_date  # type: ignore
from sqlalchemy.schema import ForeignKeyConstraint  # type: ignore
from sqlalchemy.ext.declarative import declared_attr, declarative_base  # type: ignore

from .base import config

Base: typing.Any = declarative_base()
"""Base class for :py:mod:`sqlalchemy` models."""

Base.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def update_from_kwargs(self, **kwargs):
    """Update a model object from given keyword arguments."""
    for key, value in kwargs.items():
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            msg = f"'{self.__class__}' has no attribute named '{key}'"
            raise AttributeError(msg)


# Add update_from_kwargs method to Base to provide to all model objects.
Base.update_from_kwargs = update_from_kwargs


Jurisdiction = Enum("Texas", "Federal", name="jurisdiction_enum")
"""Alias for inmate jurisdiction :py:class:`sqlalchemy.types.Enum`.

Columns of this type store the jurisdiction level of the inmate.
Currently, this must be either 'Texas' or 'Federal', but
the supported list may be extended to include other jurisdictions in the future
(for example, other states or counties).

"""


class ReleaseDate(String):
    """Inmate release date SQLAlchemy column type.

    Sometimes "release dates" returned from the providers are not dates at all;
    instead, they are strings like "LIFE SENTENCE" or "UNKNOWN". To handle
    these cases, we model release dates as a
    :py:class:`sqlalchemy.types.String` type but override the
    :py:meth:`sqlalchemy.types.String.result_processor` method used to
    postprocess values extracted from the database. In particular, when a value
    is extracted from this column, the following happens:

    1. We process the string value as a :py:class:`sqlalchemy.types.Date`.
    2. If this fails, we process the value as a :py:class:`sqlalchemy.types.String`.

    :note: This column type subclasses :py:class:`sqlalchemy.types.String`
           without overriding :py:func:`__init__` and thus uses the same inputs.

    """

    # pylint: disable=unused-argument
    def result_processor(self, dialect, coltype):
        """Return result processor."""
        super_result_processor = super().result_processor(dialect, coltype)

        def identity(value):
            return value

        process_string = super_result_processor or identity

        def process(value):
            try:
                return str_to_date(value)
            except ValueError:
                return process_string(value)

        return process


class Inmate(Base):
    """SQLAlchemy ORM model for inmate data.

    This model contains all of the inmate data pulled from various sources.
    Further, it maintains associations with other types of inmate data, such as
    inmate requests and the unit where the inmate is located.

    """

    __tablename__ = "inmates"

    # Primary key.

    jurisdiction = Column(Jurisdiction, primary_key=True)
    """Prison system holding the inmate."""

    id = Column(Integer, primary_key=True)
    """Inmate's numeric identifier as used in their jurisdiction."""

    # Person-specific data.

    first_name = Column(String)
    """Inmate first name.

    In some cases, this is given by the provider; in others cases, it is parsed
    from the full name using :py:class:`nameparser.parser.HumanName`.

    """

    last_name = Column(String)
    """Inmate last name.

    In some cases, this is given as-is by the provider; in others cases, it is
    parsed from the full name using :py:class:`nameparser.parser.HumanName`.

    """

    sex = Column(String)
    """Inmate gender as reported by provider."""

    race = Column(String)
    """Inmate race as reported by provider."""

    # TDCJ-assigned fields.

    url = Column(String)
    """Inmate URL where their information is web accessible."""

    release = Column(ReleaseDate)
    """Date of when this inmate is set to be released."""

    unit_id = Column(Integer, ForeignKey("units.id"), default=None)
    """Foreign key into the table corresponding to :py:class:`Unit`.

    Only used to resolve the relationship to :py:class:`Unit`.

    """

    unit = relationship("Unit", uselist=False, back_populates="inmates")
    """Prison unit holding the inmate."""

    # IBP-specific fields.

    datetime_fetched = Column(DateTime)
    """Datetime when inmate data was fetched from provider."""

    lookups = relationship("Lookup", order_by="desc(Lookup.datetime)")
    """List of lookups performed on this inmate by IBP volunteers."""

    comments = relationship("Comment", order_by="desc(Comment.datetime)")
    """List of comments on this inmate made by IBP volunteers."""

    requests = relationship(
        "Request", order_by="desc(Request.date_postmarked)", back_populates="inmate"
    )
    """List of requests made by this inmate."""

    @classmethod
    def from_response(cls, session, response):
        """Construct a :py:class:`Inmate` object from `pymates` response.

        This is a convenience classmethod for constructing Inmate objects from
        provider responses.

        :param session: Current sqlalchemy session.
        :param response: Response from inmate data provider.

        :returns: Constructed :py:class:`Inmate` object.

        """
        kwargs = dict(response)
        kwargs["id"] = int(kwargs["id"].replace("-", ""))
        kwargs["unit"] = session.query(Unit).filter_by(name=kwargs["unit"]).first()
        return Inmate(**kwargs)

    def db_entry_is_stale(self):
        """Calculate if an inmate database entry is stale based on configuration."""
        try:
            age = datetime.now() - self.datetime_fetched
        except TypeError:
            return True

        ttl = timedelta(hours=config.getint("warnings", "inmates_cache_ttl"))
        return age > ttl


class HasInmateIndexKey:
    """Mix-In for injecting an Inmate + index key.

    This mix-in does the following:

        - It injects an inmate jurisdiction + id + unique index primary key.
        - It adds a foreign key constraint for the :py:class:`Inmate` table.

    Injecting these attributes via inheritance is done using the
    :py:class:`sqlalchemy.ext.declarative.declared_attr` decorator class.

    In other words, any class that inherits from this mix-in will have the
    following columns added to it:

        - :py:data:`inmate_jurisdiction`
        - :py:data:`inmate_id`
        - :py:data:`index`

    where these columns form a compound key and further the combination of
    :py:data:`inmate_jurisdiction` and :py:data:`inmate_id` form a foreign-key
    into the table corresponding to the :py:class:`Inmate` model.

    """

    # pylint: disable=no-self-argument, no-self-use

    @declared_attr
    def __table_args__(cls):
        """Declare ForeignKeyConstraint attribute into inmates table."""
        return (
            ForeignKeyConstraint(
                ["inmate_jurisdiction", "inmate_id"],
                ["inmates.jurisdiction", "inmates.id"],
            ),
        )

    @declared_attr
    def inmate_jurisdiction(cls):
        """Jurisdiction of corresponding inmate."""
        return Column(Jurisdiction, primary_key=True)

    @declared_attr
    def inmate_id(cls):
        """Numeric ID of corresponding inmate."""
        return Column(Integer, primary_key=True)

    @declared_attr
    def index(cls):
        """Index to disambiguate items pointing to the same inmate."""
        return Column(Integer, primary_key=True)


class Lookup(Base, HasInmateIndexKey):
    """SQLAlchemy ORM model for inmate system lookups.

    It's occasionally useful to know when a particular inmate has been looked
    up by IBP volunteers. For this reason, we maintain a lookup table that we
    update every time an inmate is looked up.

    """

    __tablename__ = "lookups"

    datetime = Column(DateTime, nullable=False)
    """Datetime of when the inmate lookup was performed."""


class Comment(Base, HasInmateIndexKey):
    """SQLAlchemy ORM model comments on a particular inmates.

    It's useful to be able to store comments on inmates. These comments can
    include whether an inmate is a mass requester or if they have a preferred
    pronoun. In addition to the body of the comment, we also store the datetime
    that the comment was made, and the author of the comment.

    """

    __tablename__ = "comments"

    datetime = Column(DateTime, nullable=False)
    """Datetime of when the comment was made."""

    author = Column(String, nullable=False)
    """The author of the comment."""

    body = Column(Text, nullable=False)
    """The body of the comment."""


class Request(Base, HasInmateIndexKey):
    """SQLAlchemy ORM model for inmate package requests.

    Receiving and processing requests for books is the bread and butter of the
    IBP process. Requests take the form of letters. These letters arrive,
    are read and processed by a volunteer, the inmate is looked up, and
    these requests are either filled or tossed depending on the status of the
    inmate. For example, if the inmate has requested more than once in a three
    month period, the extra letters are tossed out.

    The data here is designed to facilitate this process and store the results.
    Specifically, we store the date that the request was processed, as well as
    when the date was postmarked by USPS. Further, the action is stored.
    Finally, if the package is filled, then the request can be attached to a
    :py:class:`Shipment`.

    """

    __tablename__ = "requests"

    date_processed = Column(Date, nullable=False)
    """Date that the request was processed by a volunteer."""

    date_postmarked = Column(Date, nullable=False)
    """Date that the request was postmarked by the mail service."""

    Action = Enum("Filled", "Tossed", name="action_enum")
    """Alias for request action :py:class:`sqlalchemy.types.Enum`.

    Available actions right now are 'Filled' and 'Tossed':

    - 'Filled' means that a package was ordered in response to this request.
    - 'Tossed' means that the letter was thrown away without ordering a package.

    """

    action = Column(Action, nullable=False)
    """Action taken by the IBP volunteer in response to the request."""

    inmate = relationship("Inmate", uselist=False, back_populates="requests")
    """Inmate that sent the request."""

    shipment_id = Column(Integer, ForeignKey("shipments.id"))
    """Foreign key into the table corresponding to :py:class:`Shipment`.

    Only used to resolve the relationship to :py:class:`Shipment`.

    """

    autoid = Column(Integer)
    """Deprecated numeric identifier for compatibility with old labels."""

    shipment = relationship("Shipment", uselist=False, back_populates="requests")
    """Shipment containing this request's corresponding package."""


class Shipment(Base):
    """SQLAlchemy ORM model for shipments made in response to requests."""

    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True)
    """Auto-incrementing identifier to serve as primary key."""

    date_shipped = Column(Date, nullable=False)
    """Date that the shipment was made."""

    tracking_url = Column(String)
    """Shipping service tracking URL if available."""

    tracking_code = Column(String)
    """Shipping service tracking code if available."""

    weight = Column(Integer, nullable=False)
    """Weight of the shipment in ounces."""

    postage = Column(Integer, nullable=False)
    """Postage of the shipment in US cents."""

    requests = relationship("Request", back_populates="shipment")
    """Lists of requests this shipment responds to."""

    unit_id = Column(Integer, ForeignKey("units.id"), default=None)
    """Foreign key into the table corresponding to :py:class:`Unit`.

    Only used to resolve the relationship to :py:class:`Unit`.

    """

    unit = relationship("Unit", uselist=False, back_populates="shipments")
    """Unit that this shipment was sent to."""


class Unit(Base):
    """SQLAlchemy ORM model for prison units."""

    __tablename__ = "units"

    id = Column(Integer, primary_key=True)
    """Auto-incrementing identifier to serve as primary key."""

    name = Column(String, nullable=False)
    """Name of the prison unit."""

    street1 = Column(String, nullable=False)
    """Street1 of the prison unit address."""

    street2 = Column(String)
    """Street2 of the prison unit address."""

    city = Column(String, nullable=False)
    """City of the prison unit address."""

    zipcode = Column(String(12), nullable=False)
    """Zipcode of the prison unit address."""

    state = Column(String(3), nullable=False)
    """State of the prison unit address."""

    url = Column(String)
    """URL of the prison unit if available."""

    jurisdiction = Column(Jurisdiction)
    """Jurisdiction of the prison unit."""

    ShippingMethod = Enum("Box", "Individual", name="shipping_enum")
    """Alias for shipping method :py:class:`sqlalchemy.types.Enum`.

    Available shipping methods right now are 'Box' and 'Individual':

    - 'Box' means that this unit receives multiple packages in a single box.
    - 'Individual' means that a shipment must be made for each inmate package.

    """

    shipping_method = Column(ShippingMethod)
    """Shipping method to use for this prison unit."""

    inmates = relationship("Inmate", back_populates="unit")
    """List of inmates residing in this prison unit."""

    shipments = relationship("Shipment", back_populates="unit")
    """List of shipments made to this prison unit."""
