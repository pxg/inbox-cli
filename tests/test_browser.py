from unittest.mock import patch

from email_inbox.browser import open_url


def test_open_url() -> None:
    with patch("email_inbox.browser.subprocess.Popen") as popen:
        assert open_url("https://mail.google.com/") is True
    popen.assert_called_once()
