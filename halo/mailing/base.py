import os
from flask_peewee.serializer import Serializer
from peewee import Model
from mailer import Mailer, Message
from jinja2 import Environment, FileSystemLoader, Template
from email import Charset

# Default encoding mode set to Quoted Printable. Acts globally!
Charset.add_charset('utf-8', Charset.QP, Charset.QP, 'utf-8')

class BaseEmail(object):
    # override these in subclass
    mailer_settings = NotImplementedError() # dict containing smtp settings
    subject = NotImplementedError()
    sender = NotImplementedError() # from is a reserved word in python
    to = NotImplementedError()
    template = NotImplementedError()
    html_template = NotImplementedError()
    extra_context = {}

    # templates should be in the same directory as this file
    jinja2_env = Environment(loader=FileSystemLoader([
        'templates', os.path.dirname(__file__)]))

    def __init__(self, **context):
        context = dict(self.extra_context, **context)
        self.context = self.serialize_models(context)

    def render(self, string):
        # the mailer library reconverts to unicode before sending
        return Template(string).render(**self.context).encode('utf-8', 'ignore')

    def render_file(self, filename):
        template = self.jinja2_env.get_template(filename)
        # the mailer library reconverts to unicode before sending
        return template.render(**self.context).encode('utf-8', 'ignore')

    def serialize_models(self, obj):
        """Serialize object to dictionary if db model. Recurses dictionaries
        """
        if isinstance(obj, Model):
            return Serializer().serialize_object(obj)
        elif isinstance(obj, dict):
            return dict((key, self.serialize_models(value)) \
                         for key, value in obj.iteritems())
        else:
            return obj

    def send(self):
        message = Message(From=self.render(self.sender),
                          To=self.render(self.to),
                          Subject=self.render(self.subject),
                          charset='utf-8')
        message.Body = self.render_file(self.template)
        message.Html = self.render_file(self.html_template)

        mailer = Mailer(**self.mailer_settings)
        mailer.send(message)
