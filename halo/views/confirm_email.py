import logging
from flask import request, render_template, flash, session, url_for, \
        redirect, current_app
from itsdangerous import URLSafeTimedSerializer, \
        SignatureExpired, BadSignature, BadData
from models import User
from app import app

TEMPLATES = {
    # tells user that link is invalid or expired
    'invalid link': 'theme/invalid-link.html',
    # tells user that email has been confirmed (have a link to app home)
    'confirmed': 'theme/email-confirmed.html',
}

LINK_EXPIRY = 60*60*24*10 # 10 days

# TODO: ajax should be an argument for signal
# TODO: confirm email view

# it's important to use a different salt for each activation link
# so that user can't reuse a token for another activation link
# (eg if the token is a hash of just the user id in both cases)

# for creating an activation link
security_serializer = URLSafeTimedSerializer(
    secret_key=app.config['SECRET_KEY'],
    salt=app.config['CONFIRM_EMAIL_SALT'],
)

def get_link(user):
    """Use this function to get the link to send to user"""
    token = security_serializer.dumps([user.id, user.email])
    return url_for('confirm_email', _external=True, token=token)

def verify_link_token(token):
    try:
        user_id, email = security_serializer.loads(token, max_age=LINK_EXPIRY)
        user = User.select().where((User.id == user_id) & \
                                   (User.email == email)).get()
    except (User.DoesNotExist, BadData):
        return None
    return user

@app.route('/confirm/<token>')
def confirm_email(token):
    user = verify_link_token(token)

    if not user:
        return render_template(TEMPLATES['invalid link'],
                               redirect_to=url_for('home'))

    user.email_confirmed = True
    logging.debug('email confirmed: %s' % user.email)
    user.save()

    return render_template(TEMPLATES['confirmed'],
                           user=user, redirect_to=url_for('home'))
