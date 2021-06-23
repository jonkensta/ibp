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

from marshmallow import Schema, fields, validate  # type: ignore

from . import warnings


class UnitSchema(Schema):
    """:py:mod:`marshmallow` schema for :py:class:`ibp.models.Unit`."""

    id = fields.Int(dump_only=True)
    """Read-only auto-incrementing unit index."""

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

    date_postmarked = fields.Date(required=True)
    """USPS postmarkdate of the accompanying letter."""

    action = fields.Str(validate=validate.OneOf(["Tossed", "Filled"]), required=True)
    """Action taken on the corresponding request."""


class InmateSchema(Schema):
    """:py:mod:`marshmallow` schema for :py:class:`ibp.models.Inmate`."""

    jurisdiction = fields.Str()
    """Prison system holding the inmate."""

    id = fields.Int()
    """Inmate's numeric identifier as used in their jurisdiction."""

    first_name = fields.Str()
    """Inmate first name.

    In some cases, this is given by the provider; in others cases, it is parsed
    from the full name using :py:class:`nameparser.parser.HumanName`.

    """

    last_name = fields.Str()
    """Inmate last name.

    In some cases, this is given as-is by the provider; in others cases, it is
    parsed from the full name using :py:class:`nameparser.parser.HumanName`.

    """

    sex = fields.Str()
    """Inmate gender as reported by provider."""

    race = fields.Str()
    """Inmate race as reported by provider."""

    url = fields.URL()
    """Inmate URL where their information is web accessible."""

    release = fields.Str()
    """Date of when this inmate is set to be released."""

    release_warning = fields.Function(warnings.inmate_pending_release)
    """Warning if an inmate is to be released soon."""

    datetime_fetched = fields.Str()
    """Datetime when inmate data was fetched from provider."""

    entry_age_warning = fields.Function(warnings.inmate_entry_age)
    """Warning if an inmate's information is stale."""

    unit = fields.Nested(UnitSchema, only=["name", "url"])
    """Prison unit holding the inmate."""

    lookups = fields.Nested(LookupSchema, many=True)
    """List of lookups performed on this inmate by IBP volunteers."""

    comments = fields.Nested(CommentSchema, many=True)
    """List of comments on this inmate made by IBP volunteers."""

    requests = fields.Nested(RequestSchema, many=True)
    """List of requests made by this inmate."""


class ShipmentSchema(Schema):
    """:py:mod:`marshmallow` schema for :py:class:`ibp.models.Shipment`."""

    date_shipped = fields.Date()
    """Date that the shipment was made."""

    tracking_url = fields.Str()
    """Shipping service tracking URL if available."""

    tracking_code = fields.Str()
    """Shipping service tracking code if available."""

    weight = fields.Int()
    """Weight of the shipment in ounces."""

    postage = fields.Int()
    """Postage of the shipment in US cents."""


request = RequestSchema(unknown="EXCLUDE")
"""Schema object for marshalling single :py:class:`ibp.models.Request` objects."""

comment = CommentSchema(unknown="EXCLUDE")
"""Schema object for marshalling single :py:class:`ibp.models.Comment` objects."""

inmate = InmateSchema()
"""Schema object for marshalling single :py:class:`ibp.models.Inmate` objects."""

shipment = ShipmentSchema(unknown="EXCLUDE")
"""Schema object for marshalling single :py:class:`ibp.models.Shipment` objects."""

units = UnitSchema(many=True, only=["id", "name"])
"""Schema object for marshalling multiple :py:class:`ibp.models.Unit` objects."""

inmates = InmateSchema(
    many=True, only=["jurisdiction", "id", "first_name", "last_name", "unit.name"]
)
"""Schema object for marshalling multiple :py:class:`ibp.models.Inmate` objects."""
