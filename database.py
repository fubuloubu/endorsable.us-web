import pyrebase
from requests import exceptions as request_exceptions

# Decorator for checking if authorization is still active
def auth_required(decorated_function):
    def auth_check(self, *args, **kwargs):
        try:
            f = decorated_function(self, *args, **kwargs)
        except request_exceptions.HTTPError as error:
            if error.errno.response.status_code == 401: # Unauthorized
                self.refresh_session()
                f = decorated_function(self, *args, **kwargs)
        return f
    return auth_check
        
class Database(object):
    def __init__(self):
        config = {
            "apiKey" : "AIzaSyCGxsg4BmTj3q9ZT8y9c-hhbQ6wW8ehv9g",
            "authDomain" : "endorsable-9fa55.firebaseapp.com",
            "databaseURL" : "https://endorsable-9fa55.firebaseio.com",
            #"projectId" : "endorsable-9fa55",
            "storageBucket" : "endorsable-9fa55.appspot.com",
            #"messagingSenderId" : "660294942426"
        }
        firebase = pyrebase.initialize_app(config)
        self._auth = firebase.auth()
        self._db = firebase.database()
        self._uid = None
        self._id_token = None
        self._refresh_token = None
    
    def _set_auth_data(self, user):
        if user:
            self._uid = user['localId']
            self._id_token = user['idToken']
            self._refresh_token = user['refreshToken']
            self._timeout = user['expiresIn']
        else:
            self._uid = None
            self._id_token = None
            self._refresh_token = None
            self._timeout = None

    def _refresh_session(self):
        user = self._auth.refresh(self.refresh_token)
        self._set_auth_data(user)
        
    # Perform a login
    def login(self, formdata):
        try:
            email = formdata['email']
            password = formdata['password']
            user = self._auth.sign_in_with_email_and_password(email, password)
            self._set_auth_data(user)
            return None if self.authenticated() else 'Not sure what happened here...'
        except request_exceptions.HTTPError as error:
            if error.errno.response.status_code == 400: # EMAIL_NOT_FOUND, BAD_EMAIL, ...
                error = '''Your email or password is incorrect.
                    Please try again, or register through the registration page.'''
            return error # Login unsuccessful

    def logout(self):
        self._set_auth_data(None)

    def register(self, formdata):
        try:
            fullname = formdata['fullname']
            email = formdata['email']
            password = formdata['password']
            user = self._auth.create_user_with_email_and_password(email, password)
            self._set_auth_data(user)
            # Add user data to our db
            userdata = {"email": email, "name": fullname}
            self._set_db_data('users/' + self.get_uid(), userdata)
            return None if self.authenticated() else 'Not sure what happened here...'
        except request_exceptions.HTTPError as error:
            if error.errno.response.status_code == 400: # EMAIL_EXISTS, BAD_EMAIL, ...
                error = '''The email you provided is badly formed or already in use. 
                You should use the login page to login if you already have an account.'''
            return error # Registration unsuccessful

    # Check if session token is active
    def _is_session_expired(self):
        return self._refresh_token is None
        
    # User has authenticated and has an active session token
    def authenticated(self):
        return self._id_token is not None and not self._is_session_expired()
    
    def get_uid(self):
        if self._uid is not None:
            return self._uid
        return ''
    
    @auth_required
    def _get_db_data(self, key):
        return self._db.child(key).get(self._id_token).val()

    @auth_required
    def _set_db_data(self, key, data):
        self._db.child(key).set(data, self._id_token)

    @auth_required
    def _upd_db_data(self, key, data):
        self._db.child(key).update(data, self._id_token)
        
    @auth_required
    def _del_db_data(self, key):
        return self._db.child(key).remove(self._id_token)

    @auth_required
    def _push_db_array(self, key, data):
        self._db.child(key).push(data, self._id_token)

    def _pop_db_array(self, key):
        data = self._get_db_data(key)
        self._del_db_data(key)
        return data
    
    def _get_db_array(self, key, keyname='key', valname='val'):
        ordered_dict = self._get_db_data(key)
        if ordered_dict:
            # Actually OrderedDict, a list of tuples basically
            # so we are going to convert back to a list of dicts
            def od_to_dict(key, val):
                if isinstance(val, dict):
                    obj = val.copy()
                else:
                    obj = {}
                    obj[valname] = val
                obj[keyname] = key
                return obj
            ordered_dict = [ od_to_dict(key, val) for key, val in ordered_dict.items() ]
            return ordered_dict
        else:
            return []
