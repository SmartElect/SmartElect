jQuery("document").ready(function ($){
    var $center = $("#id_center"),
        $center_label = $('label[for="id_center"]'),
        $audience = $("#id_audience"),
        $message = $('#id_message');

    $audience.change(function(){
        // Only show the center selection if it's relevant.
        var selected = $(this).val();
        var show_center_selection = (selected == "single_center");

        if (selected == "single_center") {
            $center.show();
            $center_label.show();
        }
        else {
            $center.hide();
            $center_label.hide();
        }

        return false;
    });

    $audience.change();

  // On any change to the textarea, adjust the character count
  $message.before("<label class='right'>" + chars_used_label + " <span id='counter'>0</span></label>");
  $($message).on('change keyup paste', function(event){
    $('#counter').text($message[0].value.length);
  });



});
