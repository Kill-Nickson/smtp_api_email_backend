### SMTP API email backend for SendPulseAPI in Django

1.More natural and popular way interact with SMTP-services in django is an SMTP email backend:

+ Define next variables in a project's settings.py:
<pre>
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_USE_TLS = True
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = 'youremail@gmail.com'
EMAIL_HOST_PASSWORD = 'email_password'
EMAIL_PORT = 587
</pre>

+ And connect built-in forms, for example [a password reset form](https://learndjango.com/tutorials/django-password-reset-tutorial#:~:text=Password%20Reset%20Form&text=Now%20go%20ahead%20and%20enter,the%20button%20to%20submit%20it.&text=If%20you%20refresh%20the%20password,can%20see%20our%20new%20page.).

2.Another way available in [SendPulse](https://sendpulse.com) is interaction via API.
+ Add custom.py in your project by locating the file in next directory:
>"...\site-packages\django\core\mail\backends"


+ Define next variables in a project's settings.py:
<pre>EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
DEFAULT_FROM_EMAIL = 'your@email.com'
EMAIL_HOST_USER = 'youremail@gmail.com'
EMAIL_HOST_PASSWORD = 'email_password'
</pre>

+ And connect built-in forms, for example [a password reset form](https://learndjango.com/tutorials/django-password-reset-tutorial#:~:text=Password%20Reset%20Form&text=Now%20go%20ahead%20and%20enter,the%20button%20to%20submit%20it.&text=If%20you%20refresh%20the%20password,can%20see%20our%20new%20page.).
---
## Links:
* [SendPulseAPI github page](https://github.com/sendpulse/sendpulse-rest-api-python)
* [SendPulse examples of implementation](https://sendpulse.ua/ru/features/smtp/)
* [Django sending email documentation](https://docs.djangoproject.com/en/3.1/topics/email/)
