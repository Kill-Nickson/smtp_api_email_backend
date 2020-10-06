"""Custom email backend class."""
import os
import memcache
import logging
import base64
from hashlib import md5
import threading

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address

try:
    import simplejson as json
except ImportError:
    try:
        import json
    except ImportError:
        try:
            from django.utils import simplejson as json
        except ImportError:
            raise ImportError('A json library is required to use this python library')

logger = logging.getLogger(__name__)
logger.propagate = False
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(levelname)-8s [%(asctime)s]  %(message)s'))
logger.addHandler(ch)


class EmailBackend(BaseEmailBackend):

    def __init__(self, fail_silently=False):
        super().__init__(fail_silently=fail_silently)
        self._lock = threading.RLock()

        self.email_host_user = settings.EMAIL_HOST_LOGIN
        self.email_host_password = settings.EMAIL_HOST_PASSWORD
        self.from_email = settings.DEFAULT_FROM_EMAIL

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        with self._lock:
            num_sent = 0
            for message in email_messages:
                sent = self._send(message)
                if sent:
                    num_sent += 1
        return num_sent

    def _send(self, email_message):
        if not email_message.recipients():
            return False
        encoding = email_message.encoding or settings.DEFAULT_CHARSET
        recipients = [sanitize_address(address, encoding) for address in email_message.recipients()]
        message = email_message.message()

        # Next line simply cuts the required part of the whole message created by django built-ins
        message = str(message).split('>')[1]

        # Init connection with API
        api_proxy = PySendPulse(self.email_host_user,
                                self.email_host_password,
                                'memcached')
        
        # Send an email template for each recipient
        for recipient in recipients:
            email = {
                'subject': 'Password reset email',
                'html': '<p>' + message + '</p>',
                'text': 'Message template',
                'from': {'name': 'Name', 'email': self.from_email},
                'to': [
                    {'name': 'Jane Roe', 'email': recipient}
                ]
            }
            api_proxy.smtp_send_mail(email)
        return True


class PySendPulse:
    """
    The class is a cropped version of the class PySendPulse from a pysendpulse package. 
    The class imported into the current module due to the problems occurring when installing the package via the pip.
    Documentation: https://github.com/sendpulse/sendpulse-rest-api-python
    """
    __api_url = "https://api.sendpulse.com"
    __user_id = None
    __secret = None
    __token = None
    __token_file_path = ""
    __token_hash_name = None
    __storage_type = "FILE"
    __refresh_token = 0

    MEMCACHED_VALUE_TIMEOUT = 3600
    ALLOWED_STORAGE_TYPES = ['FILE', 'MEMCACHED']

    def __init__(self, user_id, secret, storage_type="FILE"):
        logger.info("Initialization SendPulse REST API Class")
        if not user_id or not secret:
            raise Exception("Empty ID or SECRET")

        self.__user_id = user_id
        self.__secret = secret
        self.__storage_type = storage_type.upper()
        m = md5()
        m.update("{}::{}".format(user_id, secret).encode('utf-8'))
        self.__token_hash_name = m.hexdigest()
        if self.__storage_type not in self.ALLOWED_STORAGE_TYPES:
            logger.warning("Wrong storage type '{}'. Allowed storage types are: {}".format(storage_type,
                                                                                           self.ALLOWED_STORAGE_TYPES))
            logger.warning("Try to use 'FILE' instead.")
            self.__storage_type = 'FILE'
        logger.debug("Try to get security token from '{}'".format(self.__storage_type, ))
        if self.__storage_type == "MEMCACHED":
            mc = memcache.Client(['127.0.0.1:11211'])
            self.__token = mc.get(self.__token_hash_name)
        else:  # file
            file_path = "{}{}".format(self.__token_file_path, self.__token_hash_name)
            if os.path.isfile(file_path):
                with open(file_path, 'rb') as f:
                    self.__token = f.readline()
            else:
                logger.error("Can't find file '{}' to read security token.".format(file_path))
        logger.debug("Got: '{}'".format(self.__token, ))
        if not self.__token and not self.__get_token():
            raise Exception("Could not connect to API. Please, check your ID and SECRET")

    def __get_token(self):

        logger.debug("Try to get new token from server")
        self.__refresh_token += 1
        data = {
            "grant_type": "client_credentials",
            "client_id": self.__user_id,
            "client_secret": self.__secret,
        }
        response = self.__send_request("oauth/access_token", "POST", data, False)
        if response.status_code != 200:
            return False
        self.__refresh_token = 0
        self.__token = response.json()['access_token']
        logger.debug("Got: '{}'".format(self.__token, ))
        if self.__storage_type == "MEMCACHED":
            logger.debug("Try to set token '{}' into 'MEMCACHED'".format(self.__token, ))
            mc = memcache.Client(['127.0.0.1:11211'])
            mc.set(self.__token_hash_name, self.__token, self.MEMCACHED_VALUE_TIMEOUT)
        else:
            file_path = "{}{}".format(self.__token_file_path, self.__token_hash_name)
            try:
                with open(file_path, 'w') as f:
                    f.write(self.__token)
                    logger.debug("Set token '{}' into 'FILE' '{}'".format(self.__token, file_path))
            except IOError:
                logger.warning("Can't create 'FILE' to store security token. Please, check your settings.")
        if self.__token:
            return True
        return False

    def __send_request(self, path, method="GET", params=None, use_token=True, use_json_content_type=False):

        url = "{}/{}".format(self.__api_url, path)
        method.upper()
        logger.debug("__send_request method: {} url: '{}' with parameters: {}".format(method, url, params))
        if type(params) not in (dict, list):
            params = {}
        if use_token and self.__token:
            headers = {'Authorization': 'Bearer {}'.format(self.__token)}
        else:
            headers = {}
        if use_json_content_type and params:
            headers['Content-Type'] = 'application/json'
            params = json.dumps(params)

        if method == "POST":
            response = requests.post(url, headers=headers, data=params)
        elif method == "PUT":
            response = requests.put(url, headers=headers, data=params)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, data=params)
        else:
            response = requests.get(url, headers=headers, params=params)
        if response.status_code == 401 and self.__refresh_token == 0:
            self.__get_token()
            return self.__send_request(path, method, params)
        elif response.status_code == 404:
            logger.warning("404: Sorry, the page you are looking for could not be found.")
            logger.debug("Raw_server_response: {}".format(response.text, ))
        elif response.status_code == 500:
            logger.critical(
                "Whoops, looks like something went wrong on the server. "
                "Please contact with out support tech@sendpulse.com.")
        else:
            try:
                logger.debug("Request response: {}".format(response.json(), ))
            except:
                logger.critical("Raw server response: {}".format(response.text, ))
                return response.status_code
        return response

    @staticmethod
    def __handle_result(data):

        if 'status_code' not in data:
            if data.status_code == 200:
                logger.debug("Hanle result: {}".format(data.json(), ))
                return data.json()
            elif data.status_code == 404:
                response = {
                    'is_error': True,
                    'http_code': data.status_code,
                    'message': "Sorry, the page you are looking for {} could not be found.".format(data.url, )
                }
            elif data.status_code == 500:
                response = {
                    'is_error': True,
                    'http_code': data.status_code,
                    'message': "Whoops, looks like something went wrong on the server. "
                               "Please contact with out support tech@sendpulse.com."
                }
            else:
                response = {
                    'is_error': True,
                    'http_code': data.status_code
                }
                response.update(data.json())
        else:
            response = {
                'is_error': True,
                'http_code': data
            }
        logger.debug("Handle result: {}".format(response, ))
        return {'data': response}

    @staticmethod
    def __handle_error(custom_message=None):

        message = {'is_error': True}
        if custom_message is not None:
            message['message'] = custom_message
        logger.error("Hanle error: {}".format(message, ))
        return message

    # ------------------------------------------------------------------ #
    #                              SMTP                                  #
    # ------------------------------------------------------------------ #
    def smtp_send_mail(self, email):

        logger.info("Function call: smtp_send_mail")
        if (not email.get('html') or not email.get('text')) and not email.get('template'):
            return self.__handle_error('Seems we have empty body')
        elif not email.get('subject'):
            return self.__handle_error('Seems we have empty subject')
        elif not email.get('from') or not email.get('to'):
            return self.__handle_error(
                "Seems we have empty some credentials 'from': '{}' or 'to': '{}' fields".format(email.get('from'),
                                                                                                email.get('to')))
        email['html'] = base64.b64encode(email.get('html').encode('utf-8')).decode('utf-8') if email['html'] else None
        return self.__handle_result(self.__send_request('smtp/emails', 'POST', {'email': json.dumps(email)}))


if __name__ == "__main__":
    TOKEN_STORAGE = 'memcached'
    SPApiProxy = PySendPulse('your_credentials',
                             'your_credentials',
                             TOKEN_STORAGE)
    mail = {
        'subject': 'This is the test task from REST API',
        'html': '<p>This is a test task from https://sendpulse.com/api REST API!</p>',
        'text': 'This is a test task from https://sendpulse.com/api REST API!',
        'from': {'name': 'John Doe', 'email': 'sender_email'},
        'to': [
            {'name': 'Jane Roe', 'email': 'receiver_email'}
        ]
    }
    SPApiProxy.smtp_send_mail(mail)
