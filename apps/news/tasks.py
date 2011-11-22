import uuid
from datetime import date
from urllib2 import URLError

from celery.task import task
from django.conf import settings

from responsys import Responsys, NewsletterException, UnauthorizedException
from models import Subscriber
from newsletters import *


class Update(object):
    SUBSCRIBE=1
    UNSUBSCRIBE=2
    SET=3


def parse_newsletters(record, type, newsletters, optout):
    """ Parse the newsletter data from a comma-delimited string and
    set the appropriate fields in the record """

    newsletters = [x.strip() for x in newsletters.split(',')]

    if type == Update.SUBSCRIBE or type == Update.SET:
        # Subscribe the user to these newsletters
        for nl in newsletters:
            name = newsletter_field(nl)
            if name:
                record['%s_FLG' % name] = 'N' if optout else 'Y'
                record['%s_DATE' % name] = date.today().strftime('%Y-%m-%d')

    
    if type == Update.UNSUBSCRIBE or type == Update.SET:
        # Unsubscribe the user to these newsletters
        unsubs = newsletters

        if type == Update.SET:
            # Unsubscribe to the inversion of these newsletters
            subs = set(newsletters)
            all = set(NEWSLETTER_NAMES)
            unsubs = all.difference(subs)

        for nl in unsubs:
            name = newsletter_field(nl)
            if name:
                record['%s_FLG' % name] = 'N'


@task(default_retry_delay=60) # retry in 1 minute on failure
def update_user(data, authed_email, type):
    """ Task for updating user's preferences and newsletters.
    authed_email is the email for the user pulled from the database
    with their token, if exists """

    log = update_user.get_logger()

    # validate parameters
    if not authed_email and 'email' not in data:
        log.error('No user or email provided')
 
    # parse the parameters
    record = {'EMAIL_ADDRESS_': data['email'],
              'EMAIL_PERMISSION_STATUS_': 'I'}
    
    extra_fields = {
        'format': 'EMAIL_FORMAT_',
        'country': 'COUNTRY_',
        'lang': 'LANGUAGE_ISO2',
        'locale': 'LANG_LOCALE',
        'source_url': 'SOURCE_URL'
    }

    # optionally add more fields
    for field in extra_fields.keys():
        if field in data:
            record[extra_fields[field]] = data[field]

    # setup the newsletter fields
    parse_newsletters(record,
                      type,
                      data.get('newsletters', ''),
                      data.get('optin', 'Y') != 'Y')

    # make a new token
    token = str(uuid.uuid4())

    if type == Update.SUBSCRIBE:
        # if we are subscribing and the user already exists, don't
        # update the token. otherwise create a new user with the token.
        try:
            sub = Subscriber.objects.get(email=record['EMAIL_ADDRESS_'])
            token = sub.token
        except Subscriber.DoesNotExist:
            sub = Subscriber(email=record['EMAIL_ADDRESS_'], token=token)
            sub.save()
    else:
        # if we are updating an existing user, set a new token
        sub = Subscriber.objects.get(email=authed_email)
        # sub.token = token
        # sub.save()

    record['TOKEN'] = token

    # save the user's fields
    try:
        rs = Responsys()
        rs.login(settings.RESPONSYS_USER, settings.RESPONSYS_PASS)

        if authed_email and record['EMAIL_ADDRESS_'] != authed_email:
            # email has changed, we need to delete the previous user
            rs.delete_list_members(authed_email,
                                   settings.RESPONSYS_FOLDER,
                                   settings.RESPONSYS_LIST)

        rs.merge_list_members(settings.RESPONSYS_FOLDER,
                              settings.RESPONSYS_LIST,
                              record.keys(),
                              record.values())
        
        if data.get('trigger_welcome', False) == 'Y':
            rs.trigger_custom_event(record['EMAIL_ADDRESS_'],
                                    settings.RESPONSYS_FOLDER,
                                    settings.RESPONSYS_LIST,
                                    'New_Signup_Welcome')

        rs.logout()
    except URLError, e:
        # URL timeout, try again
        update_user.retry(exc=e)
    except NewsletterException, e:
        log.error('NewsletterException: %s' % e.message)
    except UnauthorizedException, e:
        log.error('Responsys auth failure')

