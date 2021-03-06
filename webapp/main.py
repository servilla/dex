#!/usr/bin/env python

"""Dex entry point"""

import logging
import os
import pathlib
import random
import re

os.environ.setdefault("FLASK_ENV", "production")
os.environ.setdefault("FLASK_DEBUG", "0")

import flask
import flask.logging

import bokeh_server.views
import db
import dex.cache
import dex.csv_cache
import dex.exc
import dex.pasta
import dex.views.eml
import dex.views.plot
import dex.views.profile
import dex.views.subset

# Flask prints the full list of URL query params when in development mode. The DataTable
# widget sends huge queries, so to reduce the noise, we increase the logging level for
# Flask's logger here, and write a brief log record with just the URL in a
# 'before_request' handler.
logging.getLogger("werkzeug").setLevel(logging.WARNING)

root_logger = logging.getLogger("")
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(flask.logging.default_handler)

log = logging.getLogger(__name__)

app = flask.Flask(
    __name__,
    static_url_path="/static/",
    static_folder=(pathlib.Path(__file__).parent / "static")
    .resolve()
    .as_posix(),
    template_folder=(pathlib.Path(__file__).parent / "templates")
    .resolve()
    .as_posix(),
)

app.config.from_object("config")
app.debug = app.config["FLASK_DEBUG"]

app.register_blueprint(bokeh_server.views.bokeh_server)
app.register_blueprint(dex.views.profile.profile_blueprint)
app.register_blueprint(dex.views.subset.subset_blueprint)
app.register_blueprint(dex.views.plot.plot_blueprint)
app.register_blueprint(dex.views.eml.eml_blueprint)


@app.before_first_request
def register_redirect_handler():
    def handle_redirect_to_index(_):
        return flask.redirect("/", 302)

    app.register_error_handler(
        dex.exc.RedirectToIndex, handle_redirect_to_index
    )


@app.before_request
def before_request():
    log.info(f"{flask.request.method} {flask.request.path}")


@app.after_request
def after_request(response):
    if response.status_code != 200:
        log.error(f"-> {response.status}")
    return response


@app.route("/favicon.ico")
def favicon():
    return flask.send_file(
        app.config["STATIC_PATH"] / "favicon" / "favicon.ico",
        mimetype="image/x-icon",
    )


@app.route("/", methods=["GET"])
def index_get():
    return flask.render_template(
        'index.html',
        rid=None,
        entity_tup=None,
        csv_list=get_sample_data_entity_list(None),
    )

@app.route("/<path:data_url>", methods=["GET"])
def index_get_url(data_url):
    rid = db.add_entity(data_url)
    return flask.redirect(f'/dex/profile/{rid}')


@dex.cache.disk("sample_data_entity_list", "list")
def get_sample_data_entity_list(_rid, k=200):
    entity_list = get_data_entity_list(None)
    if len(entity_list) >= k:
        return sorted(random.sample(entity_list, k), key=lambda d: -d['size'])
    return entity_list


@dex.cache.disk("data_entity_list", "list")
def get_data_entity_list(_rid):
    data_entity_list = []
    for abs_path in app.config['CSV_ROOT_DIR'].glob('**/*'):
        if (not abs_path.is_file()
            or len(abs_path.suffix) != 0
            or not dex.csv_cache.is_csv(None, abs_path)
        ):
            continue
        rel_path = abs_path.relative_to(app.config['CSV_ROOT_DIR'])
        m = re.match(
            '(?P<scope_str>[^.]*).'
            '(?P<id_str>\d+).'
            '(?P<ver_str>\d+).'
            '(?P<entity_str>[0-9a-f]{32})$',
            rel_path.as_posix(),
        )
        if not m:
            continue
        d = m.groupdict()
        data_entity_list.append(
            {
                'abs_path': abs_path.as_posix(),
                'scope_str': d['scope_str'],
                'id_str': d['id_str'],
                'ver_str': d['ver_str'],
                'entity_str': d['entity_str'],
                'size': abs_path.stat().st_size,
                'status': '',
            }
        )
    return sorted(data_entity_list, key=lambda d: -d['size'])


@app.route("/sample/<path:data_url>", methods=["GET"])
def sample_get(data_url):
    rid = db.add_entity(data_url)
    return flask.redirect(f'/dex/profile/{rid}')


@app.route("/", methods=["POST"])
def index_post():
    data_url = flask.request.form['data_url']
    rid = db.add_entity(data_url)
    return flask.redirect(f"/dex/profile/{rid}")


if __name__ == "__main__":
    app.run(
        # debug=True,
        # use_debugger=False,
        # use_reloader=False,
        # passthrough_errors=True,
    )

