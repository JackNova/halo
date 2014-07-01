from flask import render_template
from app import app

@app.errorhandler(404)
def page_not_found(e):
    return render_template('theme/404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('theme/500.html'), 500

@app.route('/test-500/')
def test_500():
    raise ValueError()
