# -*- coding: utf-8 -*-

""":mod:`mulre.web.yarn` --- Yarn pages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
import json

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)

from ..yarn import Tag, User, Yarn
from .db import session
from .redis import redis
from .user import get_user


ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

bp = Blueprint('yarn', __name__)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


@bp.route('/', methods=['POST'])
def add_yarn():
    content = request.form['content']
    remote_addr = request.remote_addr
    if not content:
        flash(u"내용을 입력해 주세요")
        return redirect(request.referrer)
    user = get_user(remote_addr)
    if not user:
        user = User(remote_addr=remote_addr)
    yarn = Yarn(content=content, author=user)
    for name in set(request.form['tags'].split()):
        tag = session.query(Tag).filter_by(name=name).first()
        if not tag:
            yarn.tags.append(Tag(name=name))
        else:
            yarn.tags.append(tag)
    session.add(yarn)
    session.flush()
    if request.files:
        file = request.files['file']
        if file and allowed_file(file.filename):
            yarn.filename = request.files['file'].filename
            yarn.from_blob(request.files['file'].read())
    session.commit()
    redis.publish('firehose', json.dumps({
        'content': yarn.content,
        'filename': yarn.filename,
        'id': yarn.id,
        'tags': [tag.name for tag in yarn.tags],
        'url': yarn.get_url(),
    }))
    return redirect(request.referrer)


@bp.route('/<int:yarn_id>/', methods=['PUT'])
def edit_yarn(yarn_id):
    yarn = session.query(Yarn).get(yarn_id)
    if not yarn:
        abort(404)
    if request.remote_addr != yarn.author.remote_addr:
        abort(401)
    yarn.content = request.form['content']
    yarn.tags = []
    for name in set(request.form['tags'].split()):
        tag = session.query(Tag).filter_by(name=name).first()
        if not tag:
            yarn.tags.append(Tag(name=name))
        else:
            yarn.tags.append(tag)
    session.add(yarn)
    session.commit()
    return redirect(url_for('yarn.get_yarn', yarn_id=yarn.id))


@bp.route('/<int:yarn_id>/')
def get_yarn(yarn_id):
    yarn = session.query(Yarn).get(yarn_id)
    if not yarn:
        abort(404)
    return render_template('yarn.html', yarn=yarn)


@bp.route('/<int:yarn_id>/edit/')
def edit_yarn_form(yarn_id):
    yarn = session.query(Yarn).get(yarn_id)
    if not yarn:
        abort(404)
    if request.remote_addr != yarn.author.remote_addr:
        abort(401)
    return render_template('edit_yarn_form.html', yarn=yarn)


@bp.route('/<int:yarn_id>/', methods=['DELETE'])
def delete_yarn(yarn_id):
    yarn = session.query(Yarn).get(yarn_id)
    if not yarn:
        abort(404)
    if request.remote_addr == yarn.author.remote_addr:
        session.delete(yarn)
        session.commit()
    else:
        abort(401)
    return redirect(url_for('user.home'))
