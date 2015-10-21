# Python
import logging

# 3rd party
from celery.task import task
from django.conf import settings
from django.core.mail import mail_admins
from smb.SMBConnection import SMBConnection

# This project
from civil_registry.models import DumpFile


logger = logging.getLogger(__name__)


@task
def look_for_new_dumps():
    # Try to access CRADMZShare using Samba from here
    # and see if there are any dump files we have not seen before.
    try:
        logger.info("Starting to look for new dumps...")
        creds = settings.CRA_SAMBA_CREDENTIALS
        conn = SMBConnection(
            username=creds['username'],
            password=creds['password'],
            my_name=creds['client_machine_name'],
            remote_name=creds['server_name'],
            use_ntlm_v2=True
        )
        assert conn.connect(creds['server_ip'], 139)

        new_files = []
        files = conn.listPath('share', '/')
        for file in files:
            if not file.isDirectory:
                dumpfile, created = DumpFile.objects.get_or_create(
                    filename=file.filename
                )
                if created:
                    new_files.append(file.filename)
                    logger.info("Found a new dump %s" % file.filename)
                else:
                    logger.info("File already known: %s" % file.filename)
        if new_files:
            logger.info("Sending email about new files")
            mail_admins(
                "New dump files spotted",
                "New files: %s" % ', '.join(new_files),
            )
        else:
            logger.info("No new files")
    except:
        logger.exception("Something went wrong while checking for new dump files")
