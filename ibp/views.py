import logging
from datetime import datetime, date

import flask
from flask import url_for, redirect, flash, jsonify
from flask import render_template, render_template_string

from flask_login import login_user, logout_user, current_user

import ibp

from . import models
from . import oauth2
from . import warnings
from . import flask_forms


app = ibp.app
session = ibp.db.session
login_manager = ibp.login_manager

logger = logging.getLogger('flask')


@app.route('/')
def index():
    logger.debug("loading index")
    return render_template('index.html')


@app.route('/view_log')
def view_log():
    logger.debug("loading log")
    ibp.log_handler.flush()
    log = ibp.log_stream.lines
    return render_template('view_log.html', log=log)


@app.route('/inmates', methods=['GET', 'POST'])
def search_inmates():
    form = flask_forms.InmateSearchForm()

    if flask.request.method == 'GET':
        logger.debug("loading search_inmates")
        return render_template('search_inmates.html', form=form)

    if form.validate():
        first = form.first_name.data
        last = form.last_name.data

        if first and last:
            first = form.first_name.data
            last = form.last_name.data
            inmates, errors = models.Inmate.query_by_name(first, last)
        else:
            id_ = form.id_.data
            inmates, errors = models.Inmate.query_by_inmate_id(id_)

    else:
        return render_template('search_inmates.html', form=form)

    if errors:
        logger.debug("one or more providers returned a request exception")

    for error in errors:
        flash(error, 'alert-warning')

    inmates = inmates.all()  # get all results from inmates query

    if not inmates:
        logger.debug("no search results; loading search_inmates")
        flask.flash("no inmates matched your search", 'alert-warning')
        return render_template('search_inmates.html', form=form)

    elif len(inmates) == 1:
        logger.debug("loading single search result in view_inmate")
        inmate = inmates[0]
        return redirect(url_for('view_inmate', autoid=inmate.autoid))

    else:
        logger.debug("loading search results in list_inmates")
        return render_template('list_inmates.html', inmates=inmates)


@app.route('/view_inmate/<int:autoid>')
def view_inmate(autoid):
    inmate = models.Inmate.query_by_autoid(autoid).first_or_404()
    logger.debug(
        "loading view_inmate for %s inmate #%08d",
        inmate.jurisdiction, inmate.id
    )

    del inmate.lookups[2:]
    inmate.lookups.append(datetime.now())
    session.commit()

    inmate = models.Inmate.query_by_autoid(autoid).one()
    postmarkdate = flask.session.get('postmarkdate')
    comment_form = flask_forms.Comment()

    return render_template(
        'view_inmate.html',
        inmate=inmate, postmarkdate=postmarkdate, date_today=date.today(),
        comment_form=comment_form
    )


@app.route('/add_request/<int:inmate_autoid>', methods=['POST'])
def add_request(inmate_autoid):
    inmate = models.Inmate.query_by_autoid(inmate_autoid).first_or_404()

    date_str = flask.request.form.get('postmarkdate', '')
    try:
        postmarkdate = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return "Please enter the USPS postmark date on the envelope.", 400
    else:
        flask.session['postmarkdate'] = postmarkdate.strftime("%Y-%m-%d")

    action = flask.request.form.get('action', 'Filled')

    request = models.Request(
        action=action,
        date_postmarked=postmarkdate,
        date_processed=date.today(),
        inmate=inmate
    )
    inmate.requests.append(request)
    session.commit()

    logger.debug(
        "adding request #%d with %s postmark for %s inmate #%08d",
        request.autoid, postmarkdate, inmate.jurisdiction, inmate.id
    )

    request = models.Request.query.filter_by(autoid=request.autoid).one()
    rendered_request = render_template('request.html', request=request)

    data = dict(request_autoid=str(request.autoid), request=rendered_request)
    return jsonify(data)


@app.route('/inmate_alerts/<int:autoid>')
def inmate_alerts(autoid):
    inmate = models.Inmate.query.filter_by(autoid=autoid).first_or_404()

    logger.debug(
        "checking alerts for %s inmate #%08d",
        inmate.jurisdiction, inmate.id
    )

    if not inmate.alerts:
        logger.debug(
            "no alerts were found for %s inmate #%08d",
            inmate.jurisdiction, inmate.id
        )
        return ''

    logger.debug(
        "alerts were found for %s inmate #%08d",
        inmate.jurisdiction, inmate.id
    )

    for alert in inmate.alerts:
        alert.notify()

    template = """
        The following people have set an alert for this inmate:
        <ul>
            {% for alert in alerts -%}
            <li>{{ alert.requester }}</li>
            {%- endfor %}
        </ul>
        Please write their name(s) on this letter and set it aside for them.
        They have been alerted that this letter was received, and
        they will process this request at a later time.
        Thank you very much for your assistance!
    """
    template = template.strip()

    return render_template_string(template, alerts=inmate.alerts)


@app.route('/request_warnings/<int:autoid>', methods=['POST'])
def request_warnings(autoid):
    inmate = models.Inmate.query.filter_by(autoid=autoid).first_or_404()

    date_str = flask.request.form.get('postmarkdate', '')
    try:
        postmarkdate = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return "Please enter the USPS postmark date on the envelope.", 400
    else:
        flask.session['postmarkdate'] = postmarkdate.strftime("%Y-%m-%d")

    logger.debug(
        "checking warnings for %s inmate #%08d, postmarkdate %s",
        inmate.jurisdiction, inmate.id, postmarkdate
    )

    messages = []
    messages.extend(warnings.inmate(inmate))
    messages.extend(warnings.request(inmate, postmarkdate))

    if not messages:
        logger.debug(
            "no warnings found for %s inmate #%08d, postmarkdate %s",
            inmate.jurisdiction, inmate.id, postmarkdate
        )
        return ''

    logger.debug(
        "warnings were found for %s inmate #%08d, postmarkdate %s",
        inmate.jurisdiction, inmate.id, postmarkdate
    )

    template = """
        <ul>
            {% for message in messages %}
            <li>{{ message }}</li>
            {% endfor %}
        </ul>
    """
    template = template.strip()

    return render_template_string(template, messages=messages)


@app.route('/request_label/<int:autoid>', methods=['POST'])
def request_label(autoid):
    request = models.Request.query.filter_by(autoid=autoid).first_or_404()
    logger.debug("rendering label for request #%d", autoid)
    return render_template('request_label.xml', request=request)


@app.route('/request_info/<int:autoid>')
def request_info(autoid):
    request = models.Request.query.filter_by(autoid=autoid).first_or_404()
    logger.debug("fetching information for request #%d", autoid)

    if request.inmate is None:
        return "Request does not have an associated inmate", 400

    inmate = request.inmate
    unit = inmate.unit

    return jsonify({
        'inmate_jurisdiction': inmate.jurisdiction,
        'inmate_name': inmate.last_name + ', ' + inmate.first_name,
        'inmate_id': '%08d' % inmate.id,
        'package_id': request.autoid,
        'unit_name': unit and unit.street1 or 'N/A',
        'unit_shipping_method': unit and unit.shipping_method or 'N/A',
    })


@app.route('/delete_request/<int:autoid>', methods=['DELETE'])
def delete_request(autoid):
    request = models.Request.query.filter_by(autoid=autoid).first_or_404()
    logger.debug("deleting request #%d", autoid)
    session.delete(request)
    session.commit()
    return ''


@app.route('/add_comment/<int:inmate_autoid>', methods=['POST'])
def add_comment(inmate_autoid):
    inmate = models.Inmate.query_by_autoid(inmate_autoid).first_or_404()
    form = flask_forms.Comment()

    if form.validate():
        comment = models.Comment.from_form(form)
        inmate.comments.append(comment)
        session.commit()

        logger.debug(
            "adding comment #%d for %s inmate #%08d",
            comment.autoid, inmate.jurisdiction, inmate.id
        )

        comment = render_template('comment.html', comment=comment)
        fieldset = render_template('comment_fieldset.html', comment_form=form)
        data = dict(comment=comment, fieldset=fieldset)
        return jsonify(data)

    else:
        fieldset = render_template('comment_fieldset.html', comment_form=form)
        return fieldset, 400


@app.route('/delete_comment/<int:autoid>', methods=['DELETE'])
def delete_comment(autoid):
    comment = models.Comment.query.filter_by(autoid=autoid).first_or_404()
    logger.debug("deleting comment #%d", autoid)
    session.delete(comment)
    session.commit()
    return ''


@app.route('/list_units')
def list_units():
    logger.debug("loading list_units")
    return render_template('list_units.html', units=models.Unit.query)


@app.route('/view_unit/<int:autoid>', methods=['GET', 'POST'])
def view_unit(autoid):
    unit = models.Unit.query.filter_by(autoid=autoid).first_or_404()
    form = flask_forms.Unit()

    if flask.request.method == 'GET':
        logger.debug("loading view_unit for %s Unit", unit.name)
        form.update_from_model(unit)

    elif form.validate():
        unit.update_from_form(form)
        session.commit()
        logger.debug("posting updates on %s Unit", unit.name)
        flask.flash("unit successfully updated", 'alert-success')

    return render_template('view_unit.html', form=form, unit=unit)


@ibp.csrf.exempt
@app.route('/return_address', methods=['POST'])
@ibp.appkey_required
def return_address():
    logger.debug("loading return_address view")
    address = ibp.get_config_section('address')
    return jsonify(address)


@ibp.csrf.exempt
@app.route('/request_address/<int:autoid>', methods=['POST'])
@ibp.appkey_required
def request_address(autoid):
    logger.debug("loading request_address view for request %d", autoid)
    request = models.Request.query.filter_by(autoid=autoid).first_or_404()

    inmate = request.inmate
    inmate.try_fetch_update()

    unit = inmate.unit
    if unit is None:
        return "inmate is not assigned to a unit", 400

    inmate_name = "{} {} #{:08d}".format(
        inmate.first_name.title(), inmate.last_name.title(), inmate.id
    )

    return jsonify({
        'name': inmate_name,
        'street1': unit.street1,
        'street2': unit.street2,
        'city': unit.city,
        'state': unit.state,
        'zipcode': unit.zipcode,
    })


@ibp.csrf.exempt
@app.route('/unit_autoids', methods=['POST'])
@ibp.appkey_required
def unit_autoids():
    logger.debug("loading unit_autoids view")
    autoids = {unit.name: unit.autoid for unit in models.Unit.query}
    return jsonify(autoids)


@ibp.csrf.exempt
@app.route('/unit_address/<int:autoid>', methods=['POST'])
@ibp.appkey_required
def unit_address(autoid):
    logger.debug("loading unit_address view for unit %d", autoid)
    unit = models.Unit.query.filter_by(autoid=autoid).first_or_404()
    name = ibp.config.get('shipping', 'unit_address_name')

    return jsonify({
        'name': name,
        'street1': unit.street1,
        'street2': unit.street2,
        'city': unit.city,
        'state': unit.state,
        'zipcode': unit.zipcode,
    })


@ibp.csrf.exempt
@app.route('/request_destination/<int:autoid>', methods=['POST'])
@ibp.appkey_required
def request_destination(autoid):
    logger.debug("loading request_destination view for request %d", autoid)
    request = models.Request.query.filter_by(autoid=autoid).first_or_404()

    inmate = request.inmate
    inmate.try_fetch_update()

    unit = inmate.unit
    if unit is None:
        msg = "inmate %d is not assigned to a unit".format(inmate.autoid)
        logger.debug(msg)
        return msg, 400

    return jsonify(dict(name=unit.name))


@ibp.csrf.exempt
@app.route('/ship_requests', methods=['POST'])
@ibp.appkey_required
def ship_requests():
    logger.debug("loading ship_requests view")

    form = flask_forms.Shipment(data=flask.request.form)
    form.csrf_token.data = form.csrf_token.current_token

    if not form.validate():
        return "form data invalid", 400

    request_ids = set(form.request_ids.data)

    def get_request_from_autoid(autoid):
        return models.Request.query.filter_by(autoid=autoid).first_or_404()

    requests = map(get_request_from_autoid, request_ids)
    unit = next(r.inmate.unit for r in requests if r.inmate.unit is not None)

    for request in requests:
        inmate = request.inmate
        inmate.try_fetch_update()

        if inmate.unit is None:
            msg = "inmate for request %d is unassigned".format(request.autoid)
            logger.debug(msg)
            return msg, 400

        if inmate.unit.name != unit.name:
            msg = "inmates are not all assigned to '{}' unit".format(unit.name)
            logger.debug(msg)
            return msg, 400

    shipment = models.Shipment(
        requests=requests, date_shipped=date.today(), unit=unit,
        weight=form.weight.data, postage=form.postage.data,
        tracking_code=form.tracking_code.data,
    )
    session.add(shipment)
    session.commit()

    logger.debug(
        "created %d ounce(s) shipment %d", form.weight.data, shipment.autoid
    )
    return jsonify(dict())


@app.route('/login/google')
def authorized():
    args = flask.request.args

    error = args.get('error')
    if error:
        msg = "google returned with error: {}".format(error)
        flask.flash(msg, 'alert-danger')
        return redirect(url_for('index'))

    flow = oauth2.flow_from_config()
    google = flow.step2_exchange(args['code'])
    user = models.User.from_google(google)
    session.commit()

    login_user(user)
    logger.debug("successfully logged in '%s'", current_user.email)
    flask.flash("successfully logged in!", 'alert-success')
    next_ = flask.request.args.get('state')
    return redirect(next_ or url_for('search_inmates'))


@app.route('/login')
def login():
    flow = oauth2.flow_from_config()
    next_ = flask.request.args.get('next')
    url = flow.step1_get_authorize_url(state=next_)
    return redirect(url)


login_manager.login_view = 'login'
login_manager.login_message = None


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


login_manager.logout_view = 'logout'


@login_manager.user_loader
def load_user(email):
    return models.User.get(email)


@login_manager.unauthorized_handler
def unauthorized():
    try:
        email = current_user.email
    except AttributeError:
        msg = "Anonymous login attempt failed"
    else:
        msg = "'{}' is not authorized for access".format(email)

    logger.debug(msg)
    flask.flash(msg, 'alert-danger')
    return redirect(url_for('index'))


@ibp.app.route('/metrics')
def metrics():
    """
    Handles a GET request for the package metrics page.
    """
    return render_template('metrics.html')


@ibp.app.route('/metrics/request_counts')
def request_counts():
    """
    Handles an AJAX request for the package counts by month.
    """
    sql = """
        SELECT strftime('%Y-%m', date_postmarked) as yearmonth, count(*)
        FROM requests
        WHERE
            action = 'Filled' AND
            strftime('%Y', date_postmarked) >= '2006-06'
        GROUP BY yearmonth
        ORDER BY date_postmarked ASC;
    """
    rows = ibp.db.engine.execute(sql).fetchall()
    dates = [r[0] for r in rows]
    counts = [r[1] for r in rows]

    data = dict(dates=dates, counts=counts)
    return jsonify(data)


@ibp.app.route('/metrics/new_request_counts')
def new_request_counts():
    """
    Handles an AJAX request for the number of first-timers by month.
    """
    sql = """
        SELECT yearmonth, count(*)
        FROM (
            SELECT min(strftime('%Y-%m', date_postmarked)) as yearmonth
            FROM requests
            WHERE
                action = 'Filled' AND
                strftime('%Y', date_postmarked) >= '2006-06'
            GROUP BY inmate_autoid
        )
        GROUP BY yearmonth
        ORDER BY yearmonth ASC;
    """
    rows = ibp.db.engine.execute(sql).fetchall()
    dates = [r[0] for r in rows]
    counts = [r[1] for r in rows]

    data = dict(dates=dates, counts=counts)
    return jsonify(data)


@ibp.app.route('/metrics/shipping_volume')
def shipping_volume():
    sql = """
        SELECT
            STRFTIME('%Y-%m', date_shipped) AS yearmonth,
            SUM(weight) as volume
        FROM shipments
        WHERE strftime('%Y', date_shipped) >= '2006-06'
        GROUP BY yearmonth
        ORDER BY date_shipped ASC;
    """
    rows = ibp.db.engine.execute(sql).fetchall()
    dates = [r[0] for r in rows]
    pounds = [r[1] // 16 for r in rows]  # convert from ounces

    data = dict(dates=dates, pounds=pounds)
    return jsonify(data)
