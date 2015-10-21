/*global $ */
(function set_language_js() {
  "use strict";

  var select_language = function select_language(language) {
    $('form#libya-set-language input#language-code').val(language);
    $('form#libya-set-language').submit();
  };
  $('#set-language-en').on('click', function () {
    select_language('en');
  });
  $('#set-language-ar').on('click', function () {
    select_language('ar');
  });
}());
