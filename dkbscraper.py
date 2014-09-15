#!/usr/bin/env python
# encoding: utf-8

# This file is in the Public Domain as specified by
# http://creativecommons.org/publicdomain/zero/1.0/

import requests
import lxml.html
import getpass
import bs4
import collections
import tempfile
import shutil
import os
import os.path


PostboxDocument = collections.namedtuple(
    'PostboxDocument',
    [
        'title',
        'is_read',
        'url',
        'filename',
    ]
)


class DKBSession(object):
    """
    DKB Session

    Usage
    -----

    >>> import readline
    >>> dkbs = dkbscraper.DKBSession()
    >>> dkbs.login(input("Username: "))
    >>> documents = list(dkbs.postbox_items())
    >>> dkbs.download_document(documents[10], ['test.pdf'])
    >>> dkbs.logout()
    """

    base_url = 'https://banking.dkb.de'
    login_url = '/dkb/-?$javascript=disabled'

    def __init__(self, verbose=True):

        # Initialize HTTP session
        self.s = requests.Session()

        self.verbose = verbose

    def login(self, username):
        """
        Login to DKB Online Banking
        """

        if self.verbose:
            print('Login to DKB Online Banking')

        # Get DKB Banking login page
        r = self.s.get(self.base_url + self.login_url)
        login_page = lxml.html.fromstring(r.text)

        # Get DKB Banking login form
        login_form = login_page.forms[0]

        # Fill in username and password
        login_form.fields['j_username'] = username
        login_form.fields['j_password'] = getpass.getpass()

        # Post login
        r = self.s.post(
            self.base_url + login_form.action,
            data=dict(login_form.fields)
        )

        # Parse returned page
        soup = bs4.BeautifulSoup(r.text)

        if not soup.find(text='Finanzstatus'):
            raise RuntimeError('Login to DKB Online Banking failed.')

        self.logout_url = soup.find('a', id='logout')['href']
        self.postbox_url = soup.find(id="valueOut")['href']

        if self.verbose:
            print('Logged in to DKB Online Banking')

        return True

    def logout(self):
        """
        Logout from DKB Online Banking
        """

        if self.verbose:
            print('Log out from DKB Online Banking')

        r = self.s.get(self.base_url + self.logout_url)
        ret = r.status_code == 200
        self.s.close()

        return ret

    def postbox_items(self):
        """
        Iterate over the postbox items
        """

        # Get Postbox page
        r = self.s.get(self.base_url + self.postbox_url)

        # Parse Postbox page
        soup = bs4.BeautifulSoup(r.text)

        # Get document table
        table = soup.find(id="documentsTableOverview_outer")

        # Iterate through the documents
        for row in table.table.tbody.findChildren(name='tr'):

            # document read?
            is_read = not row.findChild(id='title').findChild('strong')

            # document title
            title = row.findChild(id='title').a.text

            # document download link
            url = row.find(title='Speichern').find_parent().get('href')

            # filename
            filename = url.split('/')[-1].split('?')[0] + '.pdf'

            yield PostboxDocument(
                is_read=is_read,
                title=title,
                url=url,
                filename=filename,
            )

    def download_document(self, document, destinations):
        """
        Download a document
        """

        url = self.base_url + document.url

        # download document
        if self.verbose:
            print("Download document '{}'".format(document.title))

        r = self.s.get(url, stream=True)

        if not r.status_code == 200:
            raise RuntimeError('Download failed.')

        r.raw.decode_content = True

        # copy http data to temporary file
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            shutil.copyfileobj(r.raw, fp)
            tmp_filename = fp.name

        # copy file to destinations
        for dest in destinations:
            if self.verbose:
                print("Copy to {}".format(dest))

            if os.path.exists(dest):
                print('"{}" already exists'.format(dest))
                continue

            shutil.copyfile(tmp_filename, dest)

        # delete temporary file
        os.unlink(tmp_filename)

        return True
