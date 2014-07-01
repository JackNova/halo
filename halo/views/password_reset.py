import logging
from flask import request, render_template, flash, session, url_for, redirect, \
        current_app
from itsdangerous import URLSafeTimedSerializer, \
        SignatureExpired, BadSignature, BadData
from wtforms import Form, validators, TextField, PasswordField
from blinker import Namespace
from models import User
from app import app

my_signals = Namespace()
reset_requested = my_signals.signal('reset-requested')

TEMPLATES = {
    # has form where user enters their email address
    # form redirects to current url and shows flash message on success or error
    #'forgot password': 'password-reset/forgot-password.html',
    # has form where user enters new password
    # form redirects to current url and shows flash message on error
    # form redirects to index and show flash message on success
    'forgot password': 'theme/forgot-password.html',
    # tells user that link is invalid or expired
    'invalid link': 'theme/invalid-link.html',
}

LINK_EXPIRY = 60*60*24*10 # 10 days

# it's important to use a different salt for each activation link
# (eg. confirm email and password reset links) so that user can't reuse
# a token for the other link if hashing the same value like user_id.

# for creating an activation link
security_serializer = URLSafeTimedSerializer(
    secret_key=app.config['SECRET_KEY'],
    salt=app.config['PASSWORD_RESET_SALT'],
)

# FUNCTIONS

def send_signal(user):
    token = security_serializer.dumps(user.id)
    link = url_for('password_reset', _external=True, token=token)
    reset_requested.send(current_app._get_current_object(),
                         user=user, link=link)

def verify_link_token(token):
    try:
        user_id = security_serializer.loads(token, max_age=LINK_EXPIRY)
        user = User.select().where(User.id == user_id).get()
    except (User.DoesNotExist, BadData):
        return None
    return user

# FORMS

class ForgotPasswordForm(Form):
    email = TextField(validators=[
        validators.Email('Not a valid email address'),
        validators.Required('An email address is required')])

class PasswordResetForm(Form):
    password = PasswordField(validators=[
        validators.Required('A password is required'),
        validators.Length(6, -1, 'Password must be at least 6 characters long')])
    confirm_password = PasswordField(validators=[
        validators.EqualTo('password', 'Confirm password does not match')])

# ROUTES

@app.route('/forgot-password/', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template(TEMPLATES['forgot password'])

    form = ForgotPasswordForm(request.form)

    if not form.validate():
        flash(form.errors.items()[0][1][0], 'error')
        # normally we should keep form data so that user doesn't have to refill
        # all fields, but for simple form it's okay
        return redirect(url_for('forgot_password'))

    data = form.data

    try:
        # TODO: also have a platform == 'Web' clause?
        user = User.select().where(User.email == data['email']).get()
    except User.DoesNotExist:
        flash('A user with that email address was not found.', 'error')
        return redirect(url_for('forgot_password'))

    send_signal(user)

    flash('An email has been sent to your address with further instructions.',
          'information')
    return redirect(url_for('forgot_password'))

@app.route('/password-reset/<token>', methods=['GET', 'POST'])
def password_reset(token):
    user = verify_link_token(token)

    if not user:
        return render_template(TEMPLATES['invalid link'])

    if request.method == 'GET':
        return render_template(TEMPLATES['forgot password'], user=user, token=token)

    form = PasswordResetForm(request.form)

    if not form.validate():
        flash(form.errors.items()[0][1][0], 'error')
        # normally we should keep form data so that user doesn't have to refill
        # all fields, but for simple form it's okay
        return redirect(url_for('password_reset', token=token))

    data = form.data

    user.set_password(data['password'])
    user.save()

    # user shouldn't be logged in but force logout just in case
    session.clear()

    flash('Your password has been changed. Please login using your new password.',
          'success')
    return redirect(url_for('index'))

#"""
#Templates required:
#    1) forgot-password.html
#        has form where user enters their email address
#        redirects to current url and shows flash message on success or error
#            "An email has been sent to your address with further instructions"
#    2) password-reset.html
#        has form where user enters new password
#        redirects to current url and shows flash message on error
#            "Password must be at least x characters long"
#        redirects to home and show flash message on success
#            "Your password has been changed. Please login using your new password."
#    3) invalid-link.html
#        tells user that link is invalid or expired
#            "This link is invalid os has expired"
#"""
