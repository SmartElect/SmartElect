from django.conf.urls import url, include

from register.views import SMSBread, StaffPhoneBread, delete_all_staff_phones, \
    BlacklistedNumberBread, upload_blacklisted_numbers, download_blacklisted_numbers, \
    delete_all_blacklisted_numbers, \
    WhitelistedNumberBread, upload_whitelisted_numbers, download_whitelisted_numbers, \
    delete_all_whitelisted_numbers


urlpatterns = (
    # /sms:
    url(r'', include(BlacklistedNumberBread().get_urls())),
    url(r'', include(WhitelistedNumberBread().get_urls())),
    url(r'', include(StaffPhoneBread().get_urls())),
    url(r'', include(SMSBread().get_urls())),

    # Non-BREAD operations on black/whitelisted numbers
    url(r'^blacklisted-numbers/delete/$', delete_all_blacklisted_numbers,
        name='blacklisted-numbers-delete'),
    url(r'^blacklistednumbers/upload/$', upload_blacklisted_numbers,
        name='blacklisted-numbers-upload'),
    url(r'^blacklistednumbers/download/$', download_blacklisted_numbers,
        name='blacklisted-numbers-download'),
    url(r'^whitelisted-numbers/delete/$', delete_all_whitelisted_numbers,
        name='whitelisted-numbers-delete'),
    url(r'^whitelistednumbers/upload/$', upload_whitelisted_numbers,
        name='whitelisted-numbers-upload'),
    url(r'^whitelistednumbers/download/$', download_whitelisted_numbers,
        name='whitelisted-numbers-download'),

    url(r'^staffphones/delete/$', delete_all_staff_phones,
        name='staffphones-delete'),

)
