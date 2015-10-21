from django.test import TestCase
from text_messages.forms import MessageTextForm


class MessageTextFormTestCase(TestCase):
    def test_validation_braces_ok(self):
        data = {
            'number': '1',
            'label': 'PLAYTIME',
            'msg_en': 'The {PET} played with the {TOY}',
            'msg_ar': 'The {PET} played with the {TOY} in Arabic',
            'enhanced_en': 'The {PET} played with the {TOY} {NUMBER} times',
            'enhanced_ar': 'The {PET} played with the {TOY} {NUMBER} times in Arabic',
        }
        form = MessageTextForm(data=data)
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_validation_percents_ok(self):
        data = {
            'number': '1',
            'label': 'PLAYTIME',
            'msg_en': 'The %(PET)s played with the %(TOY)s',
            'msg_ar': 'The %(PET)s played with the %(TOY)s in Arabic',
            'enhanced_en': 'The %(PET)s played with the %(TOY)s %(NUMBER)d times',
            'enhanced_ar': 'The %(PET)s played with the %(TOY)s %(NUMBER)d times in Arabic',
        }
        form = MessageTextForm(data=data)
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_validation_braces_missing(self):
        data = {
            'number': '1',
            'label': 'PLAYTIME',
            'msg_en': 'The {PET} played with the {TOY}',
            'msg_ar': 'The {PET} played with it in Arabic',
            'enhanced_en': 'The {PET} played with the {TOY} {NUMBER} times',
            'enhanced_ar': 'The {PET} played with the {TOY} {NUMBER} times in Arabic',
        }
        form = MessageTextForm(data=data)
        self.assertFalse(form.is_valid())

    def test_validation_percents_missing(self):
        data = {
            'number': '1',
            'label': 'PLAYTIME',
            'msg_en': 'The %(PET)s played with the %(TOY)s',
            'msg_ar': 'The %(PET)s played with the %(TOY)s in Arabic',
            'enhanced_en': 'The %(PET)s played with the %(TOY)s %(NUMBER)d times',
            'enhanced_ar': 'The %(PET)s played with it %(NUMBER)d times in Arabic',
        }
        form = MessageTextForm(data=data)
        self.assertFalse(form.is_valid())

    def test_validation_braces_different(self):
        data = {
            'number': '1',
            'label': 'PLAYTIME',
            'msg_en': 'The {PET} played with the {TOY}',
            'msg_ar': 'The {PET} played with the {BABY} in Arabic',
            'enhanced_en': 'The {PET} played with the {TOY} {NUMBER} times',
            'enhanced_ar': 'The {PET} played with the {TOY} {NUMBER} times in Arabic',
        }
        form = MessageTextForm(data=data)
        self.assertFalse(form.is_valid())

    def test_validation_message_with_mixed_placeholders(self):
        data = {
            'number': '1',
            'label': 'PLAYTIME',
            'msg_en': 'The {PET} played with the {TOY}',
            'msg_ar': 'The {PET} played with the {TOY} in Arabic',
            'enhanced_en': 'The {PET} played with the {TOY} {NUMBER} times',
            'enhanced_ar': 'The %(PET)s played with the {TOY} {NUMBER} times in Arabic',
        }
        form = MessageTextForm(data=data)
        self.assertFalse(form.is_valid())

    def test_validation_messages_use_different_placeholders(self):
        data = {
            'number': '1',
            'label': 'PLAYTIME',
            'msg_en': 'The {PET} played with the {TOY}',
            'msg_ar': 'The {PET} played with the {TOY} in Arabic',
            'enhanced_en': 'The %(PET)s played with the %(TOY)s %(NUMBER)d times',
            'enhanced_ar': 'The {PET} played with the {TOY} {NUMBER} times in Arabic',
        }
        form = MessageTextForm(data=data)
        self.assertFalse(form.is_valid())
