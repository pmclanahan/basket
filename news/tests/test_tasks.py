from urllib2 import URLError

from django.test import TestCase
from django.test.utils import override_settings

from mock import Mock, patch

from news.backends.exacttarget_rest import ETRestError, ExactTargetRest
from news.celery import app as celery_app
from news.models import FailedTask
from news.newsletters import clear_sms_cache
from news.tasks import (
    add_sms_user,
    et_task,
    mogrify_message_id,
    NewsletterException,
    RECOVERY_MESSAGE_ID,
    send_recovery_message_task,
    SUBSCRIBE,
    update_phonebook,
    update_user,
)


class FailedTaskTest(TestCase):
    """Test that failed tasks are logged in our FailedTask table"""

    @patch('news.tasks.get_user_data')
    def test_failed_task_logging(self, mock_get_user_data):
        """Failed task is logged in FailedTask table"""
        mock_get_user_data.side_effect = Exception("Test exception")
        self.assertEqual(0, FailedTask.objects.count())
        args = [{'arg1': 1, 'arg2': 2}]
        kwargs = {'token': 3}
        result = update_phonebook.apply(args=args, kwargs=kwargs)
        fail = FailedTask.objects.get()
        self.assertEqual('news.tasks.update_phonebook', fail.name)
        self.assertEqual(result.task_id, fail.task_id)
        self.assertEqual(args, fail.args)
        self.assertEqual(kwargs, fail.kwargs)
        self.assertEqual(u"Exception('Test exception',)", fail.exc)
        self.assertIn("Exception: Test exception", fail.einfo)


class RetryTaskTest(TestCase):
    """Test that we can retry a task"""
    @patch('django.contrib.messages.info', autospec=True)
    def test_retry_task(self, info):
        TASK_NAME = 'news.tasks.update_phonebook'
        failed_task = FailedTask(name=TASK_NAME,
                                 task_id=4,
                                 args=[1, 2],
                                 kwargs={'token': 3},
                                 exc='',
                                 einfo='')
        # Failed task is deleted after queuing, but that only works on records
        # that have been saved, so just mock that and check later that it was
        # called.
        failed_task.delete = Mock(spec=failed_task.delete)
        with patch.object(celery_app, 'send_task') as send_task_mock:
            # Let's retry.
            failed_task.retry()
        # Task was submitted again
        send_task_mock.assert_called_with(TASK_NAME, args=[1, 2], kwargs={'token': 3})
        # Previous failed task was deleted
        self.assertTrue(failed_task.delete.called)


@patch('news.tasks.send_message', autospec=True)
@patch('news.utils.look_for_user', autospec=True)
class RecoveryMessageTask(TestCase):
    def setUp(self):
        self.email = "dude@example.com"

    def test_unknown_email(self, mock_look_for_user, mock_send):
        """Email not in basket or ET"""
        # Should log error and return
        mock_look_for_user.return_value = None
        send_recovery_message_task(self.email)
        self.assertFalse(mock_send.called)

    def test_et_error(self, mock_look_for_user, mock_send):
        """Error talking to Basket. I'm shocked, SHOCKED!"""
        mock_look_for_user.side_effect = NewsletterException('ET has failed to achieve.')

        with self.assertRaises(NewsletterException):
            send_recovery_message_task(self.email)

        self.assertFalse(mock_send.called)

    def test_email_in_et(self, mock_look_for_user, mock_send):
        """Email not in basket but in ET"""
        # Should trigger message. We can follow the user's format and lang pref
        format = 'T'
        lang = 'fr'
        mock_look_for_user.return_value = {
            'status': 'ok',
            'email': self.email,
            'format': format,
            'country': '',
            'lang': lang,
            'token': 'USERTOKEN',
            'newsletters': [],
        }
        send_recovery_message_task(self.email)
        message_id = mogrify_message_id(RECOVERY_MESSAGE_ID, lang, format)
        mock_send.delay.assert_called_with(message_id, self.email,
                                           'USERTOKEN', format)


class UpdateUserTests(TestCase):
    def _patch_tasks(self, attr, **kwargs):
        patcher = patch('news.tasks.' + attr, **kwargs)
        setattr(self, attr, patcher.start())
        self.addCleanup(patcher.stop)

    def setUp(self):
        self._patch_tasks('get_or_create_user_data')
        self._patch_tasks('get_user_data')
        self._patch_tasks('parse_newsletters', return_value=([], []))
        self._patch_tasks('apply_updates')
        self._patch_tasks('confirm_user')
        self._patch_tasks('send_welcomes')
        self._patch_tasks('send_confirm_notice')

    def self_test_success_no_token_create_user(self):
        """
        If no token is provided, use get_or_create_user_data to find (and
        possibly create) a user with a matching email.
        """
        subscriber = Mock(email='a@example.com', token='mytoken')
        self.lookup_subscriber.return_value = subscriber, None, False
        self.get_user_data.return_value = None

        update_user({}, 'a@example.com', None, SUBSCRIBE, True)
        self.get_user_data.assert_called_with(token='mytoken')


@override_settings(ET_CLIENT_ID='client_id', ET_CLIENT_SECRET='client_secret')
@patch('news.newsletters.SMS_MESSAGES', {'foo': 'bar'})
class AddSMSUserTests(TestCase):
    def setUp(self):
        clear_sms_cache()
        patcher = patch.object(ExactTargetRest, 'send_sms')
        self.send_sms = patcher.start()
        self.addCleanup(patcher.stop)

    def test_send_name_invalid(self):
        """If the send_name is invalid, return immediately."""
        add_sms_user('baffle', '8675309', False)
        self.assertFalse(self.send_sms.called)

    def test_retry_on_error(self):
        """If an ETRestError is raised while sending an SMS, retry."""
        error = ETRestError()
        self.send_sms.side_effect = error

        with patch.object(add_sms_user, 'retry') as retry:
            add_sms_user('foo', '8675309', False)
            self.send_sms.assert_called_with(['8675309'], 'bar')
            retry.assert_called_with(exc=error)

    def test_success(self):
        add_sms_user('foo', '8675309', False)
        self.send_sms.assert_called_with(['8675309'], 'bar')

    def test_success_with_optin(self):
        """
        If optin is True, add a Mobile_Subscribers record for the
        number.
        """
        with patch('news.tasks.ExactTargetDataExt') as ExactTargetDataExt:
            with self.settings(EXACTTARGET_USER='user', EXACTTARGET_PASS='asdf'):
                add_sms_user('foo', '8675309', True)

            ExactTargetDataExt.assert_called_with('user', 'asdf')
            data_ext = ExactTargetDataExt.return_value
            call_args = data_ext.add_record.call_args

            self.assertEqual(call_args[0][0], 'Mobile_Subscribers')
            self.assertEqual(set(['Phone', 'SubscriberKey']), set(call_args[0][1]))
            self.assertEqual(['8675309', '8675309'], call_args[0][2])


class ETTaskTests(TestCase):
    def test_retry_increase(self):
        """
        The delay for retrying a task should increase geometrically by a
        power of 2. I really hope I said that correctly.
        """
        error = URLError(reason=Exception('foo bar!'))

        @et_task
        def myfunc():
            raise error

        myfunc.push_request(retries=4)
        myfunc.retry = Mock()
        # have to use run() to make sure our request above is used
        myfunc.run()

        myfunc.retry.assert_called_with(exc=error, countdown=16 * 60)
