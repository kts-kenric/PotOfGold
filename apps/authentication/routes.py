# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import uuid


import json
from datetime import datetime

from flask_restx import Resource, Api

import flask
from flask import render_template, redirect, request, url_for
from flask_login import (
    current_user,
    login_user,
    logout_user
)

from flask_dance.contrib.github import github

from apps import db, login_manager
from apps.authentication import blueprint
from apps.authentication.forms import LoginForm, CreateAccountForm
from apps.authentication.models import Users
from apps.models import Reports

from apps.authentication.util import verify_pass, generate_token

# Bind API -> Auth BP
api = Api(blueprint)


# def generate_unique_id():
#     unique_id = uuid.uuid4()
#     unique_id = str(unique_id)[-3:]
#     return unique_id
#     # unique_id = str(uuid.uuid4())
#     # return unique_id


@blueprint.route('/')
def route_default():
    return redirect(url_for('authentication_blueprint.login'))

# Login & Registration

@blueprint.route("/github")
def login_github():
    """ Github login """
    if not github.authorized:
        return redirect(url_for("github.login"))

    res = github.get("/user")
    return redirect(url_for('home_blueprint.index'))

# User Page
@blueprint.route('/user')
def user_page():
    return render_template('custom/user.html')

# userRewards
@blueprint.route('/userRewards')
def user_rewards():
    return render_template('custom/userRewards.html')

# User Page
@blueprint.route('/userphoto')
def picutre_page():
    # Get the phoneNumber value from the URL
    phone = request.args.get('phoneNumber')
    # Insert a new row into the 'Users' table
    new_user = Users(phone=phone, points=0)
    db.session.add(new_user)
    db.session.commit()

    return render_template('custom/userphoto.html')

# Insert Repoert Detail into Reports Table
@blueprint.route('/insert', methods=['POST'])
def insert():
    # Get the form data from the request
    title = request.form.get('title')
    description = request.form.get('description')
    category = request.form.get('category')
    location = request.form.get('location')
    base64_image = request.form.get('base64_image')
    phone = request.form.get('phoneNumber')

    # Create a new 'Reports' object
    new_report = Reports(
        title=title,
        description=description,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        base64_image=base64_image,
        category=category,
        location=location,
        phone=phone,
        status='Open'
    )

    # Add the new object to the database
    db.session.add(new_report)

    # Commit the changes
    db.session.commit()

    # Redirect to a success page or perform any other desired action
    return render_template('custom/userphoto.html')

# Admin Page
@blueprint.route('/admin')
def admin_page():
    # Select every row from the 'Reports' table
    reports = Reports.query.all()

    # Print for debugging
    for report in reports:
        print(report.title, report.description, report.created_at, report.updated_at)
    
    return render_template('custom/admin.html', reports=reports)

# Review Page
@blueprint.route('/admin/review/<int:id>')
def review_page(id):
    report = Reports.query.get(id)
    return render_template('custom/review.html', report=report)

# Pending Page
@blueprint.route('/admin/pending', methods=['POST'])
def pending_page():
    id = request.form['id']
    report = Reports.query.get(id)
    report.status = "Pending"
    db.session.commit()
    return redirect(url_for('authentication_blueprint.admin_page'))
    # return render_template('custom/review.html', report=report)

# Approved Page
@blueprint.route('/admin/approved', methods=['POST'])
def approved_page():
    id = request.form['id']
    phone = request.form['phoneNumber']
    report = Reports.query.get(id)
    report.status = "Approved"
    # Add 5 points to the user based on the phone number
    user = Users.query.filter_by(phone=phone).first()
    print(user.points)
    user.points += 5
    db.session.commit()
    return redirect(url_for('authentication_blueprint.admin_page'))
    # return render_template('custom/review.html', report=report)

@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm(request.form)

    if flask.request.method == 'POST':

        # read form data
        username = request.form['username']
        password = request.form['password']

        #return 'Login: ' + username + ' / ' + password

        # Locate user
        user = Users.query.filter_by(username=username).first()

        # Check the password
        if user and verify_pass(password, user.password):
            login_user(user)
            return redirect(url_for('authentication_blueprint.route_default'))

        # Something (user or pass) is not ok
        return render_template('accounts/login.html',
                               msg='Wrong user or password',
                               form=login_form)

    if current_user.is_authenticated:
        return redirect(url_for('home_blueprint.index'))
    else:
        return render_template('accounts/login.html',
                               form=login_form) 


@blueprint.route('/register', methods=['GET', 'POST'])
def register():
    create_account_form = CreateAccountForm(request.form)
    if 'register' in request.form:

        username = request.form['username']
        email = request.form['email']

        # Check usename exists
        user = Users.query.filter_by(username=username).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Username already registered',
                                   success=False,
                                   form=create_account_form)

        # Check email exists
        user = Users.query.filter_by(email=email).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Email already registered',
                                   success=False,
                                   form=create_account_form)

        # else we can create the user
        user = Users(**request.form)
        db.session.add(user)
        db.session.commit()

        # Delete user from session
        logout_user()

        return render_template('accounts/register.html',
                               msg='User created successfully.',
                               success=True,
                               form=create_account_form)

    else:
        return render_template('accounts/register.html', form=create_account_form)

@api.route('/login/jwt/', methods=['POST'])
class JWTLogin(Resource):
    def post(self):
        try:
            data = request.form

            if not data:
                data = request.json

            if not data:
                return {
                           'message': 'username or password is missing',
                           "data": None,
                           'success': False
                       }, 400
            # validate input
            user = Users.query.filter_by(username=data.get('username')).first()
            if user and verify_pass(data.get('password'), user.password):
                try:

                    # Empty or null Token
                    if not user.api_token or user.api_token == '':
                        user.api_token = generate_token(user.id)
                        user.api_token_ts = int(datetime.utcnow().timestamp())
                        db.session.commit()

                    # token should expire after 24 hrs
                    return {
                        "message": "Successfully fetched auth token",
                        "success": True,
                        "data": user.api_token
                    }
                except Exception as e:
                    return {
                               "error": "Something went wrong",
                               "success": False,
                               "message": str(e)
                           }, 500
            return {
                       'message': 'username or password is wrong',
                       'success': False
                   }, 403
        except Exception as e:
            return {
                       "error": "Something went wrong",
                       "success": False,
                       "message": str(e)
                   }, 500


@blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('authentication_blueprint.login')) 

# Errors

@login_manager.unauthorized_handler
def unauthorized_handler():
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(403)
def access_forbidden(error):
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('home/page-404.html'), 404


@blueprint.errorhandler(500)
def internal_error(error):
    return render_template('home/page-500.html'), 500
