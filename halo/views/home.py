from urllib import urlencode
from flask import Flask, render_template, request, redirect, \
        session, url_for, abort, flash
from models import User, UserAccount
from app import app

"""
Views for the web interface
"""

@app.context_processor
def inject_plans():
    return dict(plans=User.PLANS_LIST, plan_features=User.PLANS)

@app.route('/')
def index():
    if session.get('user'):
        return redirect(url_for('home'))
    else:
        return render_template('index.html')

@app.route('/home/')
@app.route('/home/<path:path>/')
def home(path=None):
    if path:
        # reloading url paths currently not supported in client javascript
        return redirect(url_for('home'))

    try:
        #assert session['logged_in']
        user_id = session['user']
        user, accounts = UserAccount.from_user(user_id)
    except (KeyError, AssertionError, User.DoesNotExist, UserAccount.DoesNotExist):
        session.clear()
        return redirect(url_for('index'))

    user = user.__jsonify__()
    accounts = [account.__jsonify__() for account in accounts]

    return render_template('home.html', user=user, accounts=accounts)
