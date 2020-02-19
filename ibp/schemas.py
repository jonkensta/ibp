""":py:mod:`marshmallow` schemas for :py:mod:`ibp.models`.

The following schema classes and their corresponding instances are used in this
project to serialize Python objects to and from JSON representations.

The way that marshmallow works is that you can instantiate schema classes and
use the resulting object to (de)serialize Python objects. In this module, we
define a number of schema classes that correspond to the model classes defined
in :py:mod:`ibp.models`. In addition, we also create a number of convenience
instances of these classes that can be used directly without needing to
instantiate anything.

:note: See :py:mod:`marshmallow` for more details on marshalling.

"""

# pylint: disable=invalid-name, too-few-public-methods

from datetime import datetime

from marshmallow import Schema, fields, validate, pre_dump


class UnitSchema(Schema):
    """:py:mod:`marshmallow` schema for :py:class:`ibp.models.Unit`."""

    name = fields.Str()
    """Unit name encoded as a string."""

    url = fields.URL()
    """Unit URL if available."""


class LookupSchema(Schema):
    """:py:mod:`marshmallow` schema for :py:class:`ibp.models.Lookup`."""

    datetime = fields.DateTime(required=True)
    """Datetime of the volunteer lookup for an inmate."""


class CommentSchema(Schema):
    """:py:mod:`marshmallow` schema for :py:class:`ibp.models.Comment`."""

    index = fields.Int(dump_only=True)
    """Read-only auto-incrementing comment index."""

    datetime = fields.DateTime(dump_only=True)
    """Datetime of when the comment was made."""

    author = fields.Str(validate=validate.Length(min=1), required=True)
    """Author of the comment."""

    body = fields.Str(validate=validate.Length(min=1), required=True)
    """Body of the comment."""


class RequestSchema(Schema):
    """:py:mod:`marshmallow` schema for :py:class:`ibp.models.Request`."""

    index = fields.Int(dump_only=True)
    """Read-only auto-incrementing request index."""

    date_postmarked = fields.DateTime(required=True)
    """USPS postmarkdate of the accompanying letter."""

    action = fields.Str(validate=validate.OneOf(["Tossed", "Filled"]), required=True)
    """Action taken on the corresponding request."""

    # pylint: disable=unused-argument, no-self-use
    @pre_dump
    def convert_date(self, data, many, **kwargs):
        """Convert postmark date to a datetime before dumping to JSON."""

        def convert_date_to_datetime(date):
            return datetime.combine(date, datetime.min.time())

        data.date_postmarked = convert_date_to_datetime(data.date_postmarked)

        return data


class InmateSchema(Schema):
    """:py:mod:`marshmallow` schema for :py:class:`ibp.models.Inmate`."""

    jurisdiction = fields.Str()
    id = fields.Int()

    first_name = fields.Str()
    last_name = fields.Str()

    sex = fields.Str()
    url = fields.URL()
    race = fields.Str()
    release = fields.Str()

    unit = fields.Nested(UnitSchema, only=["name", "url"])
    lookups = fields.Nested(LookupSchema, many=True)
    comments = fields.Nested(CommentSchema, many=True)
    requests = fields.Nested(RequestSchema, many=True)


request = RequestSchema(unknown="EXCLUDE")
"""Schema object for marshalling single :py:class:`ibp.models.Request` objects."""

comment = CommentSchema(unknown="EXCLUDE")
"""Schema object for marshalling single :py:class:`ibp.models.Comment` objects."""

inmate = InmateSchema()
"""Schema object for marshalling single :py:class:`ibp.models.Inmate` objects."""

inmates = InmateSchema(
    many=True, only=["jurisdiction", "id", "first_name", "last_name", "unit.name"]
)
"""Schema object for marshalling multiple :py:class:`ibp.models.Inmate` objects."""
