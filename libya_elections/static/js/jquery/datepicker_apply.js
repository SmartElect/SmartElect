jQuery("document").ready(function ($){
  /* Use Libya's preferred date format (DD/MM/YY). 'yy' in dateFormat ==> 4 digit year.
  ref: http://en.wikipedia.org/wiki/Date_format_by_country
  ref: http://api.jqueryui.com/datepicker/#utility-formatDate
  */
  $.datepicker.setDefaults({
      'dateFormat': 'dd/mm/yy',
  });

  $(function() {
    $( ".wants_datepicker" ).datepicker();
  });
 });
