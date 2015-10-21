(function(){
  var table = $('#comparison_data tbody');
  var rows = $('#comparison_data tbody tr');
  var sliceWidth = 30;

  // init swatch colors
  rows.each(function(i){
    var swatch = $(this).find('.swatch');
    if(i === rows.length - 1)
      swatch.attr('style','background-color:'+colorArray[0]);
    else
      swatch.attr('style','background-color:'+colorArray[(i+1)%colorArray.length]);
  });

  // set click event on table
  // bubbling up through table row
  table.on('click','tr',function(){

    // the last row in the table is first in the data array
    var shiftedIndex = $(this).index() + 1;
    if(shiftedIndex === rows.length) shiftedIndex = 0;

    // update d3 state
    var state = newRegistrationsWithBars.state();
    state.disabled[shiftedIndex] = !state.disabled[shiftedIndex];

    // disable total when any other rows are selected
    // enable total when all other rows unselected
    for(var j=0, k=0; j<rows.length; j++){
      k += 1 * state.disabled[j];
    }
    if(k === rows.length){
      state.disabled[0] = false;
    }else{
      state.disabled[0] = true;
    }

    // redraw the graphs
    newRegistrationsWithBars.dispatch.changeState(state);
    cumulativeRegistrationsWithLines.dispatch.changeState(state);

    // redraw the table
    for(var i=0; i<rows.length; i++){
      // the last row in the table is first in the data array
      shiftedIndex = i + 1;
      if(shiftedIndex === rows.length) shiftedIndex = 0;

      // switch selected class on or off
      if(state.disabled[shiftedIndex]){
        $(rows[i]).removeClass('selected');
      }else{
        $(rows[i]).addClass('selected');
      }
    }
  });

  window.updateTimeline = function(end){
    // cast end to int, or use final value, if nothing supplied
    end = Math.floor(end) || newRegs[0].values.length;

    // make a slice of the data
    var newRegsSlice = [];
    var cumRegsSlice = [];

    for(var i = 0; i<newRegs.length; i++){
        var sliceA = {};
        sliceA.key = newRegs[i].key;
        sliceA.values = newRegs[i].values.slice(end - sliceWidth, end);
        newRegsSlice.push(sliceA);

      if (typeof(cumRegs) != 'undefined') {
        // cumRegs is not present on weekly chart
        var sliceB = {};
        sliceB.key = cumRegs[i].key;
        sliceB.values = cumRegs[i].values.slice(end - sliceWidth, end);
        cumRegsSlice.push(sliceB);
      }
    }

    // save the previously disabled streams
    var previous_state = newRegistrationsWithBars.state();
    var previously_disabled = previous_state.disabled.slice();

    // reload the data
    d3.select('#new-registrations-chart svg').datum(newRegsSlice).call(newRegistrationsWithBars);
    newRegistrationsWithBars.update();

    if (typeof(cumRegs) != 'undefined') {
      d3.select('#cumulative-registrations-chart svg').datum(cumRegsSlice).call(cumulativeRegistrationsWithLines);
      cumulativeRegistrationsWithLines.update();
    }

    // restore the previously disabled streams
    previous_state.disabled = previously_disabled;
    newRegistrationsWithBars.dispatch.changeState(previous_state);
    if (typeof(cumRegs) != 'undefined') {
      cumulativeRegistrationsWithLines.dispatch.changeState(previous_state);
    }
  };

  window.toLibyaDateString = function(date) {
    // Format a date in LIBYA_DATE_FORMAT: dd/mm/YYYY
    day_of_month = date.getUTCDate().toString();
    month = (date.getUTCMonth() + 1).toString();
    year = date.getUTCFullYear().toString();

    // Pad date and month, if necessary
    if (day_of_month < 10) {
      day_of_month = '0' + day_of_month;
    }
    if (month < 10) {
      month = '0' + month;
    }

    return day_of_month + '/' + month + '/' + year;
  };

  window.updateSliderValue = function(value) {
    var end_date = new Date(newRegs[0].values[value - 1].label),
        start_date = new Date(newRegs[0].values[value - sliceWidth].label);
    $('#end_date').text(toLibyaDateString(end_date));
    $('#start_date').text(toLibyaDateString(start_date));
  };

  window.setupSlider = function(){
    var numPoints = newRegs[0].values.length;
    $('#slider').attr('min', sliceWidth);
    $('#slider').attr('max', numPoints);
    $('#slider').attr('value', numPoints);
    updateSliderValue(numPoints);

    $('#slider').on("change", function() {
      updateTimeline(this.value);
      updateSliderValue(this.value);
    });
  };

  // initialize latest slice for display
  window.onload = function(){
    setTimeout(updateTimeline, 500);
  };

})();
