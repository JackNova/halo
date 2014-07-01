import logging
from flask import request, render_template, session, current_app, jsonify, redirect, url_for
from wtforms import Form, validators, TextField, PasswordField, BooleanField
from blinker import Namespace
from models import User
from app import app

my_signals = Namespace()
user_login = my_signals.signal('user-login')
new_registration = my_signals.signal('new-registration')

TEMPLATES = {
    'register': 'theme/register.html',
    'sign in': 'theme/sign-in.html',
}

# FORMS

class SignInForm(Form):
    email = TextField(validators=[
        validators.Email('Not a valid email address'),
        validators.Required('An email address is required')])
    password = PasswordField(validators=[
        validators.Required('Password is required')])
    remember = BooleanField()

class RegisterForm(Form):
    name = TextField(validators=[
        validators.Required('Your name is required')])
    email = TextField(validators=[
        validators.Email('Not a valid email address'),
        validators.Required('An email address is required')])
    password = PasswordField(validators=[
        validators.Required('A password is required'),
        validators.Length(6, -1, 'Password must be at least 6 characters long')])
    confirm = PasswordField(validators=[
        validators.EqualTo('password', 'Confirm password does not match')])
    remember = BooleanField()

# ROUTES

@app.route('/sign-in/', methods=['GET', 'POST'])
def sign_in():
    if request.method == 'GET':
        return render_template(TEMPLATES['sign in'])

    form = SignInForm(request.form)

    if not form.validate():
        # TODO: return all errors?
        error = form.errors.items()[0]
        return jsonify(field=error[0], error=error[1][0])

    data = form.data

    try:
        user = User.login_with_email(data['email'], data['password'])
    except User.DoesNotExist:
        return jsonify(field='email', error='User does not exist')
    except ValueError:
        return jsonify(field='password', error='Password incorrect')

    user_login.send(current_app._get_current_object(), user=user)

    # TODO: if on mobile return authToken

    session['user'] = user.id

    if data['remember']:
        session.permanent = True

    return jsonify(id=user.id)

@app.route('/register/', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template(TEMPLATES['register'])

    form = RegisterForm(request.form)

    if not form.validate():
        # TODO: return all errors?
        error = form.errors.items()[0]
        return jsonify(field=error[0], error=error[1][0])

    data = form.data

    if User.select().where(User.email == data['email']).count() > 0:
        return jsonify(error='Email already used', field='email')

    user = User()
    user.email = data['email']
    user.name = data['name']
    user.set_password(data['password'])
    user.save()

    new_registration.send(current_app._get_current_object(), user=user)

    # if on mobile return authToken

    session['user'] = user.id

    if data['remember']:
        session.permanent = True

    # TODO: return a 201 status code
    return jsonify(id=user.id)

@app.route('/logout/')
def logout():
    session.clear()
    return redirect(url_for('index'))
