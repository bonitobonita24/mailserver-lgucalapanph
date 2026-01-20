from wtforms import validators, fields
from flask_babel import lazy_gettext as _
import flask_wtf
import re

# Custom email validator that auto-appends domain and accepts .test TLD for development
class EmailValidator:
    def __init__(self, message=None, default_domain='lgucalapan.ph'):
        self.message = message or _('Invalid e-mail address.')
        self.pattern = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
        self.default_domain = default_domain
    
    def __call__(self, form, field):
        # Auto-append domain if not present
        if field.data and '@' not in field.data:
            field.data = field.data.strip() + '@' + self.default_domain
        if not self.pattern.match(field.data or ''):
            raise validators.ValidationError(self.message)

class LoginForm(flask_wtf.FlaskForm):
    class Meta:
        csrf = False
    email = fields.StringField(_('Username_'), [EmailValidator(), validators.DataRequired()], render_kw={'autofocus': True})
    pw = fields.PasswordField(_('Password'), [validators.DataRequired()])
    pwned = fields.HiddenField(label='', default=-1)
    submitWebmail = fields.SubmitField(_('Sign in'))
    submitAdmin = fields.SubmitField(_('Sign in'))

class PWChangeForm(flask_wtf.FlaskForm):
    oldpw = fields.PasswordField(_('Current password'), [validators.DataRequired()])
    pw = fields.PasswordField(_('New password'), [validators.DataRequired()])
    pw2 = fields.PasswordField(_('New password (again)'), [validators.DataRequired()])
    pwned = fields.HiddenField(label='', default=-1)
    submit = fields.SubmitField(_('Change password'))
