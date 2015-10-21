// httptester: submit form with 'enter' and refocus message field
(function($) {
    $(function() {
        $("#id_text").keypress(function(ev) {
            if (ev.keyCode == 13 && !ev.shiftKey) {
                $(this).closest("form").submit();
                $("#id_submit").focus();
                ev.preventDefault();
            }
        }).focus();
    });
})(jQuery);
