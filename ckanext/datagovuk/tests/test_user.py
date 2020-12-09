from bs4 import BeautifulSoup
import pytest
import unittest

import mock

from six.moves.urllib.parse import urljoin

import ckan.plugins
from ckan import model
from ckan.common import config
from ckan.tests import factories, helpers
from ckan.plugins.toolkit import url_for
from ckan.lib.mailer import MailerException, create_reset_key


# @pytest.mark.skip("no need to test as we will be using core ckan code")
@pytest.mark.usefixtures("clean_db", "with_plugins")
class TestEditUser:
    def test_edit_user_form(self, app):
        user = factories.User(password='pass1234')
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        response = app.get(
            url=url_for("user.edit"),
            extra_environ=env,
        )

        # form = response.forms['user-edit-form']
        page = BeautifulSoup(response.get_data(as_text=True), 'html.parser')
        print("*** test edit user form", page)
        form = {e['name']: e.get('value', '') for e in page.find_all('input')}
        print("*** form", form)

        # Check the existing values
        assert form['name'] == user['name']
        assert form['fullname'] == user['fullname']
        assert form['email'] == user['email']
        assert form['password1'] == ''
        assert form['password2'] == ''

        # Modify the values
        form['fullname'] = 'user fullname'
        form['email'] = 'test@test.com'
        form['old_password'] = 'pass1234'
        form['password1'] = 'Abc12345'
        form['password2'] = 'Abc12345'
        # response = submit_and_follow(app, form, env, 'save')

        # location = _get_location(response)
        # response = app.post(location,
        #     extra_environ=env,
        #     # environ_overrides=user_env, 
        #     data={
        #         "id": "",
        #         "save": "go-dataset"
        #     }
        # )

        response = app.post(
            url=url_for("user.edit"),
            extra_environ=env,
            data={
                "fullname": "user fullname",
                "email": "test@test.com",
                "save": "",
                "old_password": "pass1234",
                "password1": "Abc12345",
                "password2": "Abc12345"
            }
        )

        print('response', response.get_data(as_text=True))
        user = model.Session.query(model.User).get(user['id'])
        assert user.fullname == 'user fullname'
        assert user.email == 'test@test.com'

    def test_create_user_via_post_responds_403(self, app):
        app.post(
            url=url_for(controller='user', action='register'),
            params={
                "name": 'newuser',
                'fullname': 'New User',
                'email': 'test@gov.uk',
                'password1': 'TestPassword1',
                'password2': 'TestPassword1',
                "save": "1",
            },
            status=403
        )
        assert not model.User.by_email("test@gov.uk")

    def test_create_user_via_get_shows_dgu_register_page(self, app):
        response = app.get(
            url=url_for(controller='user', action='register'),
            status=200
        )
        assert 'https://data.gov.uk/support' in response

    def test_edit_user_form_password_too_short(self, app):
        user = factories.User(password='pass1234')
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        response = app.get(
            url=url_for("user.edit"),
            extra_environ=env,
        )

        form = response.forms['user-edit-form']

        # Modify the values
        form['old_password'] = 'pass1234'
        form['password1'] = 'Abc1234'
        form['password2'] = 'Abc1234'
        response = webtest_submit(form, 'save', status=200, extra_environ=env)

        assert 'Your password must be 8 characters or longer' in response

    def test_edit_user_form_password_no_lower_case(self, app):
        user = factories.User(password='pass1234')
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        response = app.get(
            url=url_for("user.edit"),
            extra_environ=env,
        )

        form = response.forms['user-edit-form']

        # Modify the values
        form['old_password'] = 'pass1234'
        form['password1'] = 'ABC12345'
        form['password2'] = 'ABC12345'
        response = webtest_submit(form, 'save', status=200, extra_environ=env)

        assert 'Your password must contain at least one upper and one lower case character' in response

    def test_edit_user_form_password_no_upper_case(self, app):
        user = factories.User(password='pass1234')
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        response = app.get(
            url=url_for("user.edit"),
            extra_environ=env,
        )

        form = response.forms['user-edit-form']

        # Modify the values
        form['old_password'] = 'pass1234'
        form['password1'] = 'abc12345'
        form['password2'] = 'abc12345'
        response = webtest_submit(form, 'save', status=200, extra_environ=env)

        assert 'Your password must contain at least one upper and one lower case character' in response

    def test_edit_user_form_passwords_not_matching(self, app):
        user = factories.User(password='pass1234')
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        response = app.get(
            url=url_for("user.edit"),
            extra_environ=env,
        )

        form = response.forms['user-edit-form']

        # Modify the values
        form['old_password'] = 'pass1234'
        form['password1'] = 'Abc123456'
        form['password2'] = 'Abc12345'
        response = webtest_submit(form, 'save', status=200, extra_environ=env)

        assert 'The passwords you entered do not match' in response

    def test_edit_user_form_password_missing(self, app):
        user = factories.User(password='pass1234')
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        response = app.get(
            url=url_for("user.edit"),
            extra_environ=env,
        )

        form = response.forms['user-edit-form']

        # Modify the values
        form['old_password'] = 'pass1234'
        form['password1'] = ''
        form['password2'] = ''
        response = webtest_submit(form, 'save', status=200, extra_environ=env)

        self.assertIn('Please enter both passwords', response)


@pytest.mark.usefixtures("clean_db")
class TestUserMe:
    def test_user_me_logged_in(self, app):
        user = factories.User()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        response = app.get(
            url=url_for("user.me"),
            follow_redirects=False,
            extra_environ=env,
            status=302,
        )

        assert response.location == urljoin(config.get('ckan.site_url'), url_for("dashboard.datasets"))

    def test_user_me_not_logged_in(self, app):
        response = app.get(
            url=url_for("user.me"),
            follow_redirects=False,
            status=302,
        )

        assert response.location == urljoin(config.get('ckan.site_url'), url_for("user.login"))

    def test_use_from_logged_in(self, app):
        user = factories.User()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        response = app.get(
            url=url_for("user.logged_in"),
            follow_redirects=False,
            extra_environ=env,
            status=302,
        )

        assert response.location == urljoin(config.get('ckan.site_url'), url_for("dashboard.datasets"))


@pytest.mark.skip("no need to test as we will be using core ckan code")
class TestRequestPasswordReset:
    @mock.patch('ckanext.datagovuk.lib.mailer.mailer.mail_user', autospec=True)
    def _test_request_reset_inner(self, user, user_arg, mock_mail_user):
        app = self._get_test_app()
        response = app.post(
            url=url_for("user.request_reset"),
            params={u"user": user_arg},
            status=302,
        )

        self.assertEqual(
            mock_mail_user.mock_calls,
            [mock.call(
                mock.ANY,
                u"Reset your password",
                (
                    u"You're receiving this email because you requested a new "
                    u"password for your Data publisher account for data.gov.uk."
                    u"\n\nPlease go to {} to create a new password. \n\nIf you "
                    u"didn't send us a request, you can safely ignore this email "
                    u"and use your existing sign in details.\n\nThe data.gov.uk "
                    u"team"
                ).format(urljoin(
                    config.get('ckan.site_url'),
                    url_for(
                        "user.perform_reset",
                        id=user["id"],
                        key=model.Session.query(model.User).get(user['id']).reset_key,
                    ),
                )),
            )],
        )
        self.assertEqual(mock_mail_user.mock_calls[0][1][0].id, user["id"])
        self.assertEqual(mock_mail_user.mock_calls[0][1][0].email, user["email"])

    def test_request_reset_by_email(self):
        user = factories.User(email="foo@example.com")
        self._test_request_reset_inner(user, u"foo@example.com")

    def test_request_reset_by_name(self):
        user = factories.User(name="fooman")
        self._test_request_reset_inner(user, u"fooman")

    @unittest.skip(
        "can't test because in test mode the view ends up throwing an auth audit "
        "failure that doesn't happen when served for real."
    )
    @mock.patch('ckanext.datagovuk.lib.mailer.mailer.mail_user', autospec=True)
    def test_request_reset_unknown_email(self, mock_mail_user):
        user = factories.User(email="foo@example.com")
        app = self._get_test_app()
        response = app.post(
            url=url_for("user.request_reset"),
            params={u"user": u"bar@example.com"},
            status=200,
        )

        self.assertIn("No such user", response.body)
        self.assertEqual(mock_mail_user.mock_calls, [])


    @mock.patch('ckanext.datagovuk.lib.mailer.mailer.mail_user', autospec=True)
    def test_request_reset_mailer_exception(self, mock_mail_user):
        mock_mail_user.side_effect = MailerException("bad things happened")

        user = factories.User(email="foo@example.com")
        app = self._get_test_app()
        response = app.post(
            url=url_for("user.request_reset"),
            params={u"user": u"foo@example.com"},
            status=200,
        )

        self.assertIn("Could not send reset link", response.body)
        self.assertTrue(mock_mail_user.called)


@pytest.mark.skip("no need to test as we will be using core ckan code")
class TestPerformPasswordReset:
    def _test_perform_reset_password_error_inner(self, new_password):
        params = {'password1': new_password, 'password2': new_password}
        user = factories.User()
        user_obj = model.User.by_name(user['name'])
        create_reset_key(user_obj)
        key = user_obj.reset_key
        pw_hash = user_obj.password

        app = self._get_test_app()
        response = app.post(
            url_for(
                "user.perform_reset",
                id=user_obj.id,
                key=user_obj.reset_key,
            ),
            params=params,
            status=200,
        )

        user_obj = model.User.by_name(user['name'])  # Update user_obj
        # reset_key shouldn't have been changed
        self.assertEqual(key, user_obj.reset_key)
        # password shouldn't have been changed
        self.assertEqual(pw_hash, user_obj.password)

        return response

    def test_perform_reset_password_too_short(self):
        response = self._test_perform_reset_password_error_inner("FooBar")
        self.assertIn("8 characters", response.body)

    @unittest.skip(
        "password reset view doesn't currently enforce this restriction, but "
        "it probably should for consistency with user.edit"
    )
    def test_perform_reset_password_no_caps(self):
        response = self._test_perform_reset_password_error_inner("foobarbaz1")
        self.assertIn("8 characters", response.body)


@pytest.mark.skip("no need to test as we will be using core ckan code")
class TestRegisterUser:
    def test_register_a_user_blocked(self):
        app = helpers._get_test_app()
        response = app.post(
            url_for("user.register"),
            params={
                "name": 'newuser',
                'fullname': 'New User',
                'email': 'test@gov.uk',
                'password1': 'TestPassword1',
                'password2': 'TestPassword1',
                "save": "1",
            },
            status=403,
        )
        self.assertFalse(model.User.by_email("test@gov.uk"))

    def test_get_still_works(self):
        app = helpers._get_test_app()
        response = app.get(
            url_for("user.register"),
            status=200,
        )
        self.assertIn("contact us", response.body.lower())
